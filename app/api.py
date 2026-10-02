
from fastapi import FastAPI,UploadFile,File,Form,HTTPException
import os
import logging
import uuid
from openai import APITimeoutError
from app.main import interview_graph
from pydantic import BaseModel
logger = logging.getLogger(__name__)

app = FastAPI()
class AnswerRequest(BaseModel):
    session_id: str
    curr_answer:str
@app.post("/interview/start")
async def upload_file(file: UploadFile = File(...),job_description:str=Form(...)):
    try:
        session_id = str(uuid.uuid4())
        os.makedirs("uploads", exist_ok=True)
        pdf_path = f"uploads/{session_id}.pdf"
        content = await file.read()
        with open(pdf_path, "wb") as f:
            f.write(content)
        initial_state = {"pdf_path": pdf_path,
                         "job_description": job_description,
                         "curr_question": "",
                         "curr_answer": "",
                         "interview_round": 1,
                         "prev_data": [],
                         "curr_evaluation": {},
                         "candidate_analysis": "",
                         "next_action": "",
                         "curr_topic": "",
                         "final_report": ""}
        config={"configurable":{"thread_id":session_id}}
        result = interview_graph.invoke(initial_state,config=config)

        return {"curr_question":result["curr_question"],
                "session_id":session_id,}
    except HTTPException:
        raise
    except APITimeoutError as e:
        logger.exception("模型请求超时")
        raise HTTPException(status_code=504,detail="模型请求超时,请稍后重试") from e
    except Exception as e:
        logger.exception("开始面试失败")
        raise HTTPException(status_code=500,detail="开始面试失败,请稍后重试")
@app.post("/interview/answer")
def submit_answer(answer: AnswerRequest):
    session_id=answer.session_id
    curr_answer=answer.curr_answer
    config={"configurable":{"thread_id":session_id}}

    try:
        state = interview_graph.get_state(config)
        if not state.values:
            raise HTTPException(status_code=404,detail="面试会话不存在,请重新开始")
        interview_graph.update_state(config,{"curr_answer":curr_answer})

        logger.debug("收到的session_id: %s", session_id)
        logger.debug("下一节点: %s", state.next)
        result=interview_graph.invoke(None,config=config)
        if result["final_report"]:
            return{"final_report":result["final_report"],"session_id":session_id}
        else:
            return {"curr_question":result["curr_question"],
                "session_id":session_id,"curr_evaluation":result["curr_evaluation"]}
    except HTTPException:
        raise
    except APITimeoutError as e:
        logger.exception("模型请求超时")
        raise HTTPException(status_code=504,detail="模型请求超时,请稍后重试") from e
    except Exception as e:
        logger.exception("处理面试回答失败")
        raise HTTPException(status_code=500,detail="处理面试回答时发生错误")





