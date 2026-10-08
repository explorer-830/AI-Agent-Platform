"""Opt-in synthetic model evaluation. Calls the configured paid model; no real resume/DB.
Run: python -B tests/run_model_eval.py --output <result.json>
"""
import argparse
import ast
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_scoring import load_workflow

QUESTION = "企业知识库为什么结合 BM25 和向量检索？请说明两者互补性、结果融合方法，以及如何验证效果。允许使用不同的融合方案。"
RUBRIC = {
    "requirements": [
        {"id":"r1","description":"正确解释关键词检索和语义检索的互补作用"},
        {"id":"r2","description":"给出一种合理的结果融合方法，并解释基本做法"},
        {"id":"r3","description":"说明如何比较检索效果，给出可执行的验证方法"},
    ],
    "reference_approaches":["RRF根据排名融合候选；只是示例，允许其他合理方案"],
    "error_criteria":["混淆BM25与向量检索的基本作用", "直接把未经处理的不同尺度分数相加并声称尺度完全一致"],
}
CASES = [
    ("reference", "BM25能匹配专有名词和错误码，向量检索能召回同义表达。我对两路候选去重，使用RRF按排名融合，再取top-k。准备标注相关片段的问句集，比较纯向量和混合检索的Recall@k与MRR，同时记录耗时。"),
    ("alternative", "BM25补关键词和型号，向量检索补语义改写。我的融合方式不是RRF：把两路分数在验证集上校准到可比较尺度，加权线性融合并按chunk ID去重，权重用验证集选。使用独立测试集对比纯向量的Recall@k和MRR，同时记录延迟，避免只凭几个例子判断。"),
    ("partial", "BM25可以找关键词，向量检索能处理语义相近的问题，所以把它们结合起来。"),
    ("incorrect", "BM25通过神经网络理解同义句，向量检索只匹配完全相同的字词。它们的原始分数尺度完全相同，直接相加就保证效果更好，不需要测试。"),
    ("placeholder", "2"),
]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--case", action="append", choices=[name for name, _ in CASES])
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--evaluation-only", action="store_true")
    args=parser.parse_args()
    load_dotenv(ROOT / ".env")
    workflow=load_workflow()
    workflow.client=OpenAI(api_key=os.getenv("Deepseek_API_KEY"),base_url="https://api.deepseek.com",timeout=60,max_retries=0)
    baseline_source=subprocess.check_output(["git","show","HEAD:app/main.py"],cwd=ROOT,text=True,encoding="utf-8")
    original=ast.parse(baseline_source)
    baseline_nodes=[node for node in original.body if isinstance(node,ast.FunctionDef) and node.name=="evaluate_answer"]
    baseline_namespace={"client":workflow.client,"json":json,"logger":logging.getLogger("baseline"),"InterviewState":dict}
    exec(compile(ast.Module(body=baseline_nodes,type_ignores=[]),"baseline_evaluate","exec"),baseline_namespace)
    rows=[]
    for name,answer in CASES:
        if args.case and name not in args.case:
            continue
        print("CASE",name,flush=True)
        state={"curr_question":QUESTION,"curr_answer":answer,"curr_rubric":RUBRIC}
        row={"case":name,"answer":answer}
        for label,fn in [("before",baseline_namespace["evaluate_answer"]),("after",workflow.evaluate_answer)]:
            if label == "before" and args.skip_baseline:
                continue
            try:
                row[label]=fn(state)["curr_evaluation"]
                print(label,"score",row[label]["score"],"kind",row[label].get("answer_kind"),flush=True)
            except Exception as exc:
                row[label]={"error_type":type(exc).__name__,"error":str(exc)}
                print(label,"FAILED",type(exc).__name__,flush=True)
        rows.append(row)
        Path(args.output).parent.mkdir(parents=True,exist_ok=True)
        Path(args.output).write_text(json.dumps({"question":QUESTION,"rubric":RUBRIC,"cases":rows},ensure_ascii=False,indent=2),encoding="utf-8")
    if args.evaluation_only:
        if any("error_type" in row["after"] for row in rows):
            raise SystemExit(1)
        return
    generation=workflow.generate_question({"candidate_analysis":"候选人实现过BM25、向量检索和RRF的企业知识库，目标岗位是AI应用开发实习。", "prev_data":[], "next_action":"", "curr_topic":"RAG"})
    print("question_generation_validated",flush=True)
    evaluated_history=[{"round":index,"question":QUESTION,"answer":row["answer"],"rubric":RUBRIC,"evaluation":row["after"]}
                       for index,row in enumerate(rows,1) if "score" in row["after"]]
    report=workflow.generate_report({"prev_data":evaluated_history}) if evaluated_history else None
    output={"question":QUESTION,"rubric":RUBRIC,"cases":rows,"generated_question":generation,
            "report":json.loads(report["final_report"]) if report else None,
            "limitations":"Synthetic single run; not a benchmark or proof of general improvement. Baseline default temperature, new evaluation temperature=0."}
    Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RESULT",args.output,flush=True)
    if any("error_type" in row["after"] for row in rows):
        raise SystemExit(1)

if __name__=="__main__":
    main()
