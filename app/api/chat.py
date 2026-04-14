from fastapi import FastAPI
# uvicorn app.api.chat:app --reload
app = FastAPI()

@app.get("/chat")
def chat():
    return {"Hello": "World"}
