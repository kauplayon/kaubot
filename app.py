from flask import Flask, jsonify, make_response, render_template

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


@app.after_request
def disable_page_cache(response):
    # Ensure browsers fetch the latest NEXUS interface after each deployment.
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "online", "application": "NEXUS", "version": "1.0.1"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
