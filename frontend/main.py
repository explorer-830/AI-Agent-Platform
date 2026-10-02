import streamlit as st
import requests
import json

st.markdown("""
<style>
[data-testid="stChatInput"] {
    border: 1px solid #808080;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.title("智能面试系统")
st.caption("基于简历与职位信息进行面试问答的系统")
if "interview_started" not in st.session_state:
    st.session_state["interview_started"]=False
if "interview_finished" not in st.session_state:
    st.session_state["interview_finished"]=False
if "messages" not in st.session_state:
    st.session_state["messages"]=[]
if "final_report" not in st.session_state:
    st.session_state["final_report"] = None
with st.sidebar:
    upload_file=st.file_uploader("上传简历",type="pdf")
    job_description = st.text_area("岗位信息",placeholder="请输入目标岗位的具体描述")
    start_button = st.button("开始面试")


if start_button:
    if upload_file and job_description :
        try:
            with st.spinner("正在分析JD与简历"):
                files = {"file": upload_file}
                JD = {"job_description": job_description}
                response=requests.post("http://127.0.0.1:8000/interview/start",
                                       files=files,
                                       data=JD,
                                       timeout=120)
                if response.status_code == 200:
                    st.session_state["messages"]=[]
                    st.session_state["final_report"]=None
                    data=response.json()
                    st.session_state["curr_question"]=data["curr_question"]
                    st.session_state["session_id"]=data["session_id"]
                    st.session_state["interview_started"]=True
                    st.session_state["interview_finished"]=False
                    question={"role":"assistant","content":data["curr_question"]}
                    st.session_state["messages"].append(question)

                else:
                    error_message = "开始面试失败，请稍后重试"
                    try:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            error_message = error_data.get("detail") or error_message
                    except ValueError:
                        pass
                    st.error(error_message)
        except requests.Timeout:
            st.error("开始面试请求超时，请稍后重试")
        except requests.RequestException as e:
            st.error("无法链接后端服务请检查`后端是否正常")
with st.sidebar:
    if "session_id" not in st.session_state:
        st.info("请上传简历并填写岗位信息")
    else:
        st.success("正在面试当中")

for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])
answer=None
if st.session_state["interview_started"] is False:
    st.info("请先上传简历并填写岗位信息,然后点击开始面试")
elif st.session_state["interview_finished"] is False:
    answer=st.chat_input("请输入你的回答")
else:
    st.success("本次面试结束,请查看下方评估报告")

if answer:

    user_data = {"role": "user", "content": answer}
    st.session_state["messages"].append(user_data)
    with st.chat_message("user"):
        st.write(answer)

    payload={"curr_answer":answer,"session_id":st.session_state["session_id"]}
    try:
        with st.spinner("正在分析回答"):
            response=requests.post("http://127.0.0.1:8000/interview/answer",json=payload,timeout=120)
        if response.status_code == 200:
            data=response.json()

            if "final_report" in data:
                st.session_state["interview_finished"]=True
                try:
                    final_report=json.loads(data["final_report"])
                except (json.JSONDecodeError, TypeError):
                    st.error("评估报告解析失败，请稍后重试")
                else:
                    st.session_state["final_report"]=final_report


            else:
                st.session_state["curr_evaluation"]=data["curr_evaluation"]
                curr_evaluation=st.session_state["curr_evaluation"]

                st.session_state["curr_question"] = data["curr_question"]
                evaluation_text = f"评分：{curr_evaluation['score']}，评价：{curr_evaluation['reason']}，薄弱点：{curr_evaluation['weakness']}"
                st.session_state["messages"].append({"role": "assistant", "content": evaluation_text})
                with st.chat_message("assistant"):
                    st.write(evaluation_text)
                assistant_data = {"role": "assistant", "content": data["curr_question"]}
                st.session_state["messages"].append(assistant_data)
                with st.chat_message("assistant"):
                    st.write(st.session_state["curr_question"])
        else:
            error_message = "提交回答失败，请稍后重试"
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_message = error_data.get("detail") or error_message
            except ValueError:
                pass
            if response.status_code == 404:
                st.session_state["interview_started"] = False
                st.session_state["interview_finished"] = False
                st.session_state.pop("session_id", None)
                st.error(f"会话不存在，请重新开始面试：{error_message}")
            else:
                st.error(error_message)
    except requests.Timeout:
        st.error("提交回答请求超时，请稍后重试")
    except requests.RequestException:
        st.error("无法连接后端服务，请检查后端是否正常")
if st.session_state["final_report"] is not None:
    final_report = st.session_state["final_report"]

    st.divider()
    st.title("个人面试报告")

    st.metric(
        label="综合评分",
        value=f"{final_report['综合评分']}分"
    )

    st.subheader("总体评价")
    st.write(final_report["总体评价"])

    st.subheader("优点")
    for item in final_report["优点"]:
        st.write(f"• {item}")

    st.subheader("薄弱点")
    for item in final_report["薄弱点"]:
        st.write(f"• {item}")

    st.subheader("改进建议")
    for index, item in enumerate(final_report["改进建议"], start=1):
        st.write(f"{index}. {item}")




