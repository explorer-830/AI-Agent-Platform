import os
import logging
from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from openai import OpenAI
from dotenv import load_dotenv
import json
from pypdf import PdfReader
from pypdf.errors import PdfReadError
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
logger = logging.getLogger(__name__)

load_dotenv()
client=OpenAI(base_url="https://api.deepseek.com",
              api_key=os.getenv("Deepseek_API_KEY"))

class InterviewState(TypedDict):
    pdf_path:str
    job_description:str
    curr_question:str
    curr_answer:str
    interview_round:int
    prev_data:list[dict]
    curr_evaluation:dict
    candidate_analysis:str
    next_action:str
    curr_topic:str
    final_report:str


def analyze_candidate(state:InterviewState):
    candidate=analyze_pdf(state['pdf_path'])
    job_description=state['job_description']
    response=client.chat.completions.create(model="deepseek-v4-flash",
                                            messages=[{"role":"system",
             "content":f"你是一名智能的分析助手,能够精准地分析出各种因素,"
                       f"请你根据面试者的简历{candidate}和面试者面试的工作岗位{job_description},"
                       f"精准地分析出面试者所有技能和技术栈以及工作岗位的所需技能,返回时不需要返回思考过程",


                                                                 }])
    analysis=response.choices[0].message.content
    return {"candidate_analysis":analysis}

def generate_question(state:InterviewState):
    analysis=state['candidate_analysis']
    prev_data=state['prev_data']
    next_action=state['next_action']
    curr_topic=state['curr_topic']
    response=client.chat.completions.create(model="deepseek-v4-flash",
                                            messages=[{"role":"system",
        "content":f"你是一名考虑周到的面试出题官,请你根据面试者和职位的最终分析要求"
                  f"以及之前的面试记录来决定出什么样的面试题目,要求符合面试者的简历以及职位要求"
                  f"同时也可以适当地拓展一下深度,同时也不能够太难,每次只需要出一道题目,不要重复已经出过的题目"
                  f"如果next_action是continue,则继续围绕上一轮回答的薄弱点进行追问,如果是switch_topic,则根据新的技术方向{curr_topic}进行出题提问"
                  f"这是当前的next_action:{next_action},如果next_action既不是continue也不是switch_topic则可以忽略next_action"
                  f"这里是面试者和工作职位最终的分析结果{analysis}以及之前的面试记录{prev_data},返回时不需要返回思考过程"
                  f"如果之前的面试记录为空则忽略,如果不为空则正常读取"               }])
    curr_question=response.choices[0].message.content
    return{"curr_question":curr_question}

def evaluate_answer(state:InterviewState):
    curr_question=state['curr_question']


    curr_answer=state['curr_answer']
    response=client.chat.completions.create(model="deepseek-v4-flash",
                                            messages=[
                                                {
                                                    "role": "system",
                                                    "content": f"""
        你是一名专业的技术面试评估官,请根据当前的面试问题和面试者的回答，对面试者的回答质量进行综合评估。

                    你需要重点判断：
                                1. 回答是否正确
                                2. 是否覆盖问题中的关键知识点
                                3. 回答是否具有足够的技术深度
                                4. 是否存在明显的错误或遗漏
                                5. 面试者目前是否需要继续深入考察
                                
                                请严格按照下面的 JSON 格式返回：

                                            {{
                                                "score": 0,
                                                "reason": "",
                                                "weakness": ""
                                            }}
                                           字段要求：
                                            - score：回答质量评分，必须是 0~100 的整数
                                            - reason：说明为什么给出这个分数
                                            - weakness：说明回答中存在的主要问题或薄弱点

                                            评分标准：
- 0~59：回答存在明显错误，核心知识点掌握不足，无法完成问题要求
- 60~79：回答基本正确，覆盖了主要知识点，但存在部分遗漏或深度不足
- 80~89：回答较好，已经覆盖问题中的主要要求，仅存在少量细节遗漏，可以认为当前知识点基本掌握
- 90~100：回答优秀，能够完整覆盖问题要求，并具有较好的技术深度、工程思维和实际经验

特别注意：
不要因为回答没有覆盖题目中的每一个细节就大幅扣分。
如果回答已经正确覆盖了问题的核心知识点，即使少量细节没有展开，也应该给予80分以上。
如果候选人的回答能够结合自己的实际项目进行合理说明，应适当提高评分。
不要为了继续追问而故意压低分数。
请根据回答本身客观评分。
                                            输出要求：
                                            - 必须返回合法 JSON
                                            - JSON 中的字段必须使用双引号
                                            - 不要返回 Markdown
                                            - 不要使用 ```json 包裹
                                            - 不要返回思考过程
                                            - 除 JSON 之外不要输出任何其他内容

                                    这是当前面试问题{curr_question}以及面试者回答{curr_answer}
                                            """
                                                }
                                            ])
    curr_evaluate=response.choices[0].message.content
    try:
        data=json.loads(curr_evaluate)
        data["score"]=int(data["score"])

    except json.JSONDecodeError as e:
        raise ValueError("大模型返回的不是合法JSON")from e

    except (KeyError, TypeError, ValueError) as e:
        raise ValueError("大模型返回的评分数据格式不正确") from e
    logger.debug("本题评分: %s", data["score"])
    return {"curr_evaluation": data, "curr_answer": curr_answer}

def route_interview(state:InterviewState):
    evaluation=state['curr_evaluation']
    interview_round=state['interview_round']
    score=evaluation['score']
    if interview_round > 5:
        return "end"
    elif score < 80:

        return "continue"

    elif score >=80:

        return "switch_topic"
def set_continue(state:InterviewState):
    return {"next_action":"continue"}
def update_interview_round(state:InterviewState):
    interview_round=state['interview_round']
    interview_round+=1
    return {"interview_round":interview_round}

def save_interview(state:InterviewState):
    curr_question=state['curr_question']
    interview_round=state['interview_round']
    curr_answer=state['curr_answer']
    evaluation=state['curr_evaluation']
    pre_data=state['prev_data']
    Data={"round":interview_round,
          "question":curr_question,
          "answer":curr_answer,
          "evaluation":evaluation
    }
    pre_data.append(Data)
    return {"prev_data":pre_data}

def switch_topic(state:InterviewState):
    candidate_analysis=state['candidate_analysis']
    prev_data=state['prev_data']
    curr_topic=state['curr_topic']
    response=client.chat.completions.create(model="deepseek-v4-flash",
        messages=[{"role":"system",
                   "content": f"""你是一名专业的分析者,请你根据候选人的技术栈以及岗位要求和历史面试记录,
                              选择一个尚未重点考察的新技术方向,只需要返回技术名称,不需要解释
                        这是面试者的简历:{candidate_analysis}和面试记录:{prev_data},当前技术方向:{curr_topic}"""
                   }])
    curr_topic=response.choices[0].message.content
    return {"curr_topic":curr_topic,"next_action":"switch_topic"}

def generate_report(state: InterviewState):
    prev_data = state["prev_data"]

    messages = [
        {
            "role": "system",
            "content": f"""
你是一名专业的面试评估官，请根据候选人的历史面试记录生成最终面试评估报告。

要求：
1. 综合评分为 0-100 分，参考各轮面试评分的平均值。
2. 总体评价用 2-3 句话概括候选人的整体表现。
3. 优点总结 3-5 条，只能依据面试中实际体现出的能力。
4. 薄弱点总结 3-5 条，指出需要提升的知识或能力。
5. 改进建议 3-5 条，并尽量具体、可执行。
6. 不要虚构面试记录中没有体现的信息。
7. 只返回合法 JSON，不要使用 Markdown，不要添加 JSON 以外的解释文字。

严格按照以下格式返回：
{{
    "综合评分": 0,
    "总体评价": "",
    "优点": [],
    "薄弱点": [],
    "改进建议": []
}}

候选人的历史面试记录：
{prev_data}
"""
        }
    ]

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=messages
    )

    report = response.choices[0].message.content
    try:
        json.loads(report)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError("大模型返回的报告不是合法JSON") from e

    return {"final_report": report}
def analyze_pdf(file_path:str):
    pdf_data = []
    try:
        with open(file_path,"rb") as pdf_file:
            data=PdfReader(pdf_file)
            if data.is_encrypted:
                raise ValueError("简历PDF已加密,请上传未加密的文件")
            for page in data.pages:
                text=page.extract_text()
                pdf_data.append(text or "")
    except PdfReadError as e:
        raise ValueError("无法读取简历PDF,请检查文件是否损坏") from e
    candidate = "\n".join(pdf_data)
    if not candidate.strip():
        raise ValueError("简历中没有可读取的文字,请上传文字版PDF")
    return candidate


graph=StateGraph(InterviewState)
graph.add_node("分析面试者的简历与职位信息",analyze_candidate)
graph.add_node("生成面试问题",generate_question)
graph.add_node("评估回答质量",evaluate_answer)
graph.add_node("更新回答次数",update_interview_round)
graph.add_node("更新历史数据",save_interview)
graph.add_node("选择新技术方向",switch_topic)
graph.add_node("生成个人报告",generate_report)
graph.add_node("继续追问",set_continue)

graph.add_edge(START,"分析面试者的简历与职位信息")
graph.add_edge("分析面试者的简历与职位信息","生成面试问题")
graph.add_edge("生成面试问题","评估回答质量")
graph.add_edge("评估回答质量","更新历史数据")
graph.add_edge("更新历史数据","更新回答次数")
graph.add_conditional_edges("更新回答次数",route_interview,{"continue":"继续追问",
                                                                         "switch_topic":"选择新技术方向",
                                                                          "end":"生成个人报告"})
graph.add_edge("选择新技术方向","生成面试问题")
graph.add_edge("生成个人报告",END)
graph.add_edge("继续追问","生成面试问题")
conn=sqlite3.connect("interview_checkpoints.sqlite",check_same_thread=False)
memory=SqliteSaver(conn)
interview_graph=graph.compile(checkpointer=memory,
                              interrupt_before=["评估回答质量"])





