#!/usr/bin/env python
import json
import logging
import os
import uuid

from flask import Flask, Response, request
from flask.views import View
from flask_mail import Mail, Message

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="static")
mail = Mail(app)

app.config["SECRET"] = "my secret key"
app.config["TEMPLATES_AUTO_RELOAD"] = True


def get_unique_id():
    """Generate and return a unique hex id, 13 chars long."""
    fileid = uuid.uuid4().hex[:13]
    if os.path.exists(os.path.join(config["data_path"], fileid)):
        fileid = get_unique_id()
    return fileid


def read_file_chunks(filename, chunk_size=4096):
    with open(filename) as fh:
        while True:
            data = fh.read(chunk_size)
            if not data:
                break
            yield data


def write_file(filename, name, content):
    try:
        with open(filename, "w") as f:
            f.write(content)
    except Exception:
        return Response(
            json.dumps({"status": f"unable to write {name}", "fileid": ""}),
        )


@app.route("/api/upload", methods=["POST"])
def upload():
    fields = ["cryptofile", "metadata", "deletepassword"]
    for f in fields:
        if f not in request.form:
            return Response(
                json.dumps(
                    {
                        "status": f"invalid upload request, {f} missing, error",
                        "fileid": "",
                    }
                ),
                status=400,
            )

    # get unique id for this file
    fileid = get_unique_id()
    os.mkdir(os.path.join(config["data_path"], fileid))
    cryptofile = os.path.join(config["data_path"], fileid, "cryptofile.dat")
    metadatafile = os.path.join(config["data_path"], fileid, "metadata.dat")
    serverdatafile = os.path.join(config["data_path"], fileid, "serverdata.json")

    # write encrypted file
    response = write_file(cryptofile, "cryptofile", request.form["cryptofile"])
    if response:
        return response

    # write metadata file
    response = write_file(metadatafile, "metadata", request.form["metadata"])
    if response:
        return response

    # write serverdata file
    response = write_file(
        serverdatafile,
        "serverdatafile",
        json.dumps(
            {
                "deletepassword": request.form["deletepassword"],
                "clientip": request.environ.get(
                    "HTTP_X_FORWARDED_FOR", request.remote_addr
                ),
            }
        ),
    )
    if response:
        return response

    if config["admin"]["send_email"]:
        # send email
        msg = Message(
            "new file uploaded to {request.server_name}",
            sender=config["email_sender"],
            recipients=["{config['admin']['name']} <{config['admin']['email']}>"],
        )
        msg.body = "new file uploaded to {request.server_name}: https://{request.server_name}/{fileid}"
        mail.send(msg)

    # return response
    return Response(
        json.dumps({"status": "ok", "fileid": fileid}),
    )


class FileView(View):
    def __init__(self, apicall):
        self.apicall = apicall

    def dispatch_request(self):
        self.fileid = request.args.get("fileid")
        if not self.fileid:
            return Response(
                json.dumps({"status": "missing fileid"}),
                status=400,
            )
        self.filepath = os.path.join(config["data_path"], self.fileid)
        if not os.path.exists(self.filepath):
            return Response(
                json.dumps({"fileid": self.fileid, "exists": False}), status=404
            )

        response = getattr(self, self.apicall)()
        return response

    def exists(self):
        return Response(json.dumps({"fileid": self.fileid, "exists": True}), status=200)

    def cryptofile(self):
        filename = os.path.join(self.filepath, "cryptofile.dat")
        return app.response_class(read_file_chunks(filename), mimetype="text/plain")

    def metadata(self):
        filename = os.path.join(self.filepath, "metadata.dat")
        return app.response_class(read_file_chunks(filename), mimetype="text/plain")

    def delete(self):
        pw = request.args.get("deletepassword")
        with open(os.path.join(self.filepath, "serverdata.json")) as f:
            serverdata = json.loads(f.read())
        if pw != serverdata["deletepassword"]:
            return Response(
                json.dumps({"fileid": self.fileid, "deleted": False}), status=401
            )
        for filename in ["serverdata.json", "metadata.dat", "cryptofile.dat"]:
            os.unlink(os.path.join(self.filepath, filename))
        os.rmdir(self.filepath)
        return Response(
            json.dumps({"fileid": self.fileid, "deleted": True}), status=200
        )

    def ip(self):
        with open(os.path.join(self.filepath, "serverdata.json")) as f:
            serverdata = json.loads(f.read())
        return Response(
            json.dumps({"fileid": self.fileid, "uploadip": serverdata["clientip"]}),
            status=200,
        )


app.add_url_rule(
    "/api/exists", view_func=FileView.as_view("api_exists", apicall="exists")
)
app.add_url_rule(
    "/api/file", view_func=FileView.as_view("api_cryptofile", apicall="cryptofile")
)
app.add_url_rule(
    "/api/metadata", view_func=FileView.as_view("api_metadata", apicall="metadata")
)
app.add_url_rule(
    "/api/delete", view_func=FileView.as_view("api_delete", apicall="delete")
)
app.add_url_rule("/api/ip", view_func=FileView.as_view("api_ip", apicall="ip"))

with open("config.json") as f:
    config = json.loads(f.read())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
