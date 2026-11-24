"""Standalone runner: python server.py  ->  http://localhost:5000"""
import json, os
from flask import Flask, Response
from googel_api import bp

app = Flask(__name__)
app.register_blueprint(bp)


@app.get("/")
def index():
    # Environment variables set in Render are handed to the page here (the Clerk publishable key is public by design)
    cfg = {"clerk": os.environ.get("CLERK_PUBLISHABLE_KEY", ""), "api": os.environ.get("API_URL", "")}
    page = open("index.html", encoding="utf-8").read()
    tag = "<script>window.GOOGEL=" + json.dumps(cfg).replace("<", "\\u003c") + ";</script>\n"
    return Response(page.replace("<script>", tag + "<script>", 1), mimetype="text/html")


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)))
