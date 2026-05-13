from fastapi import FastAPI

app = FastAPI(title="MedNotebook API")


@app.get("/")
def root():
    return {"status": "ok", "app": "MedNotebook API"}
