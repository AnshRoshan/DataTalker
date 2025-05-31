from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import shutil
import tempfile
import requests
from main_graph import app as langgraph_app  # Your LangGraph app

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat/")
async def chat_with_db(
    question: str = Form(...), db_file: UploadFile = None, db_url: str = Form(None)
):
    try:
        # STEP 1: Get the DB file (from upload or URL)
        temp_dir = tempfile.mkdtemp()
        db_path = None

        if db_file:
            db_path = os.path.join(temp_dir, db_file.filename)
            with open(db_path, "wb") as f:
                shutil.copyfileobj(db_file.file, f)

        elif db_url:
            if not db_url.endswith(".db"):
                return JSONResponse(
                    status_code=400,
                    content={"error": "URL must point to a `.db` file."},
                )
            db_path = os.path.join(temp_dir, "downloaded.db")
            response = requests.get(db_url)
            if response.status_code == 200:
                with open(db_path, "wb") as f:
                    f.write(response.content)
            else:
                return JSONResponse(
                    status_code=400, content={"error": f"Failed to fetch DB from URL."}
                )

        else:
            return JSONResponse(
                status_code=400, content={"error": "No DB file or URL provided."}
            )

        # STEP 2: Run through LangGraph
        state = {"question": question, "db_path": db_path}

        result = langgraph_app.invoke(state)

        # STEP 3: Return to frontend
        return {
            "answer": result.get("answer", "No answer."),
            "sql": result.get("sql", None),
            "results": result.get("results", []),
            "follow_up_questions": result.get("follow_up_questions", []),
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
