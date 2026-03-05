from core.agent import app

from core.models.response_model import ResponseModel

def response_controller(topic:str) :
    output = app.invoke({
        "topic" : topic,
        "mode":"",
        "needs_research":False,
        "queries":[],
        "evidence":[],
        "plan": None,
        "sections": [],
        "final": "",
    })
    response = ResponseModel(topic=topic, final= output.get("final", ""))
    return response