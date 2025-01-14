import json
import sure  # noqa # pylint: disable=unused-import

import moto.server as server


def test_create_without_enable_option():
    backend = server.create_backend_app("guardduty")
    test_client = backend.test_client()

    body = {"enable": "True"}
    response = test_client.post("/detector", data=json.dumps(body))
    response.status_code.should.equal(200)
    json.loads(response.data).should.have.key("detectorId")
