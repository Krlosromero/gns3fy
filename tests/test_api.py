import json
import pytest
import requests
import requests_mock
from pathlib import Path
from pydantic.error_wrappers import ValidationError
from gns3fy import Link, Node, Project, Gns3Connector
from .data import links, nodes, projects


DATA_FILES = Path(__file__).resolve().parent / "data"
BASE_URL = "mock://gns3server:3080"
CPROJECT = {"name": "API_TEST", "id": "4b21dfb3-675a-4efa-8613-2f7fb32e76fe"}
CNODE = {"name": "alpine-1", "id": "ef503c45-e998-499d-88fc-2765614b313e"}
CTEMPLATE = {"name": "alpine", "id": "847e5333-6ac9-411f-a400-89838584371b"}
CLINK = {"link_type": "ethernet", "id": "4d9f1235-7fd1-466b-ad26-0b4b08beb778"}


def links_data():
    with open(DATA_FILES / "links.json") as fdata:
        data = json.load(fdata)
    return data


def nodes_data():
    with open(DATA_FILES / "nodes.json") as fdata:
        data = json.load(fdata)
    return data


def projects_data():
    with open(DATA_FILES / "projects.json") as fdata:
        data = json.load(fdata)
    return data


def templates_data():
    with open(DATA_FILES / "templates.json") as fdata:
        data = json.load(fdata)
    return data


def version_data():
    with open(DATA_FILES / "version.json") as fdata:
        data = json.load(fdata)
    return data


def json_api_test_project():
    "Fetches the API_TEST project response"
    return next((_p for _p in projects_data() if _p["project_id"] == CPROJECT["id"]))


def json_api_test_node():
    "Fetches the alpine-1 node response"
    return next((_n for _n in nodes_data() if _n["node_id"] == CNODE["id"]))


def json_api_test_template():
    "Fetches the alpine template response"
    return next((_t for _t in templates_data() if _t["template_id"] == CTEMPLATE["id"]))


def json_api_test_link():
    "Fetches the alpine link response"
    return next((_l for _l in links_data() if _l["link_id"] == CLINK["id"]))


def post_put_matcher(request):
    resp = requests.Response()
    if request.method == "POST":
        if request.path_url.endswith("/projects"):
            # Now verify the data
            _data = request.json()
            if _data["name"] == "API_TEST":
                resp.status_code = 200
                resp.json = json_api_test_project
                return resp
            elif _data["name"] == "DUPLICATE":
                resp.status_code = 409
                resp.json = lambda: dict(
                    message="Project 'DUPLICATE' already exists", status=409
                )
                return resp
        elif request.path_url.endswith(f"/{CPROJECT['id']}/close"):
            _returned = json_api_test_project()
            _returned.update(status="closed")
            resp.status_code = 204
            resp.json = lambda: _returned
            return resp
        elif request.path_url.endswith(f"/{CPROJECT['id']}/open"):
            _returned = json_api_test_project()
            _returned.update(status="opened")
            resp.status_code = 204
            resp.json = lambda: _returned
            return resp
        elif request.path_url.endswith(f"/{CPROJECT['id']}/nodes"):
            _data = request.json()
            if not any(x in _data for x in ("compute_id", "name", "node_id")):
                resp.status_code == 400
                resp.json = lambda: dict(message="Invalid request", status=400)
                return resp
            resp.status_code = 201
            resp.json = json_api_test_node
            return resp
        elif request.path_url.endswith(
            f"/{CPROJECT['id']}/nodes/{CNODE['id']}/start"
        ) or request.path_url.endswith(f"/{CPROJECT['id']}/nodes/{CNODE['id']}/reload"):
            _returned = json_api_test_node()
            _returned.update(status="started")
            resp.status_code = 200
            resp.json = lambda: _returned
            return resp
        elif request.path_url.endswith(f"/{CPROJECT['id']}/nodes/{CNODE['id']}/stop"):
            _returned = json_api_test_node()
            _returned.update(status="stopped")
            resp.status_code = 200
            resp.json = lambda: _returned
            return resp
        elif request.path_url.endswith(
            f"/{CPROJECT['id']}/nodes/{CNODE['id']}/suspend"
        ):
            _returned = json_api_test_node()
            _returned.update(status="suspended")
            resp.status_code = 200
            resp.json = lambda: _returned
            return resp
        elif request.path_url.endswith(f"/{CPROJECT['id']}/links"):
            _data = request.json()
            nodes = _data.get("nodes")
            if len(nodes) != 2:
                resp.status_code = 400
                resp.json = lambda: dict(message="Invalid request", status=400)
                return resp
            elif nodes[0]["node_id"] == nodes[1]["node_id"]:
                resp.status_code = 409
                resp.json = lambda: dict(message="Cannot connect to itself", status=409)
                return resp
            _returned = json_api_test_link()
            resp.status_code = 201
            resp.json = lambda: _returned
            return resp
    elif request.method == "PUT":
        if request.path_url.endswith(f"/{CPROJECT['id']}"):
            _data = request.json()
            _returned = json_api_test_project()
            resp.status_code = 200
            resp.json = lambda: {**_returned, **_data}
            return resp
    return None


class Gns3ConnectorMock(Gns3Connector):
    def create_session(self):
        self.session = requests.Session()
        self.adapter = requests_mock.Adapter()
        self.session.mount("mock", self.adapter)
        self.session.headers["Accept"] = "application/json"
        if self.user:
            self.session.auth = (self.user, self.cred)

        # Apply responses
        self._apply_responses()

    def _apply_responses(self):
        # Record the API expected responses
        # Version
        self.adapter.register_uri(
            "GET", f"{self.base_url}/version", json=version_data()
        )
        # Templates
        self.adapter.register_uri(
            "GET", f"{self.base_url}/templates", json=templates_data()
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/templates/{CTEMPLATE['id']}",
            json=next(
                (_t for _t in templates_data() if _t["template_id"] == CTEMPLATE["id"])
            ),
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/templates/7777-4444-0000",
            json={"message": "Template ID 7777-4444-0000 doesn't exist", "status": 404},
            status_code=404,
        )
        # Projects
        self.adapter.register_uri(
            "GET", f"{self.base_url}/projects", json=projects_data()
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/projects/{CPROJECT['id']}",
            json=json_api_test_project(),
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/projects/{CPROJECT['id']}/stats",
            json={"drawings": 0, "links": 4, "nodes": 6, "snapshots": 0},
        )
        self.adapter.register_uri(
            "POST",
            f"{self.base_url}/projects/{CPROJECT['id']}/nodes/start",
            status_code=204,
        )
        self.adapter.register_uri(
            "POST",
            f"{self.base_url}/projects/{CPROJECT['id']}/nodes/stop",
            status_code=204,
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/projects/7777-4444-0000",
            json={"message": "Project ID 7777-4444-0000 doesn't exist", "status": 404},
            status_code=404,
        )
        self.adapter.register_uri(
            "DELETE", f"{self.base_url}/projects/{CPROJECT['id']}"
        )
        self.adapter.add_matcher(post_put_matcher)
        # Nodes
        self.adapter.register_uri(
            "GET", f"{self.base_url}/projects/{CPROJECT['id']}/nodes", json=nodes_data()
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/projects/{CPROJECT['id']}/nodes/{CNODE['id']}",
            json=next((_n for _n in nodes_data() if _n["node_id"] == CNODE["id"])),
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/projects/{CPROJECT['id']}/nodes/{CNODE['id']}/links",
            json=[
                _link
                for _link in links_data()
                for _node in _link["nodes"]
                if _node["node_id"] == CNODE["id"]
            ],
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/projects/{CPROJECT['id']}/nodes/" "7777-4444-0000",
            json={"message": "Node ID 7777-4444-0000 doesn't exist", "status": 404},
            status_code=404,
        )
        self.adapter.register_uri(
            "DELETE",
            f"{self.base_url}/projects/{CPROJECT['id']}/nodes/{CNODE['id']}",
            status_code=204,
        )
        # Links
        self.adapter.register_uri(
            "GET", f"{self.base_url}/projects/{CPROJECT['id']}/links", json=links_data()
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/projects/{CPROJECT['id']}/links/{CLINK['id']}",
            json=next((_l for _l in links_data() if _l["link_id"] == CLINK["id"])),
        )
        self.adapter.register_uri(
            "GET",
            f"{self.base_url}/projects/{CPROJECT['id']}/links/" "7777-4444-0000",
            json={"message": "Link ID 7777-4444-0000 doesn't exist", "status": 404},
            status_code=404,
        )
        self.adapter.register_uri(
            "DELETE",
            f"{self.base_url}/projects/{CPROJECT['id']}/links/{CLINK['id']}",
            status_code=204,
        )


@pytest.fixture(scope="class")
def gns3_server():
    return Gns3ConnectorMock(url=BASE_URL)


def test_Gns3Connector_wrong_server_url(gns3_server):
    # NOTE: Outside of class beacuse it changes the base_url
    gns3_server.base_url = "WRONG URL"
    with pytest.raises(requests.exceptions.InvalidURL):
        gns3_server.get_version()


class TestGns3Connector:
    def test_get_version(self, gns3_server):
        assert dict(local=True, version="2.2.0") == gns3_server.get_version()

    def test_get_templates(self, gns3_server):
        # gns3_server = Gns3ConnectorMock(url="mock://gns3server:3080")
        response = gns3_server.get_templates()
        for index, n in enumerate(
            [
                ("IOU-L3", "iou", "router"),
                ("IOU-L2", "iou", "switch"),
                ("vEOS", "qemu", "router"),
                ("alpine", "docker", "guest"),
                ("Cloud", "cloud", "guest"),
                ("NAT", "nat", "guest"),
                ("VPCS", "vpcs", "guest"),
                ("Ethernet switch", "ethernet_switch", "switch"),
                ("Ethernet hub", "ethernet_hub", "switch"),
                ("Frame Relay switch", "frame_relay_switch", "switch"),
                ("ATM switch", "atm_switch", "switch"),
            ]
        ):
            assert n[0] == response[index]["name"]
            assert n[1] == response[index]["template_type"]
            assert n[2] == response[index]["category"]

    def test_get_template_by_name(self, gns3_server):
        response = gns3_server.get_template_by_name(name="alpine")
        assert "alpine" == response["name"]
        assert "docker" == response["template_type"]
        assert "guest" == response["category"]

    def test_get_template_by_id(self, gns3_server):
        response = gns3_server.get_template_by_id(CTEMPLATE["id"])
        assert "alpine" == response["name"]
        assert "docker" == response["template_type"]
        assert "guest" == response["category"]

    def test_template_not_found(self, gns3_server):
        response = gns3_server.get_template_by_id("7777-4444-0000")
        assert "Template ID 7777-4444-0000 doesn't exist" == response["message"]
        assert 404 == response["status"]

    def test_get_projects(self, gns3_server):
        response = gns3_server.get_projects()
        for index, n in enumerate(
            [
                ("test2", "test2.gns3", "closed"),
                ("API_TEST", "test_api1.gns3", "opened"),
            ]
        ):
            assert n[0] == response[index]["name"]
            assert n[1] == response[index]["filename"]
            assert n[2] == response[index]["status"]

    def test_get_project_by_name(self, gns3_server):
        response = gns3_server.get_project_by_name(name="API_TEST")
        assert "API_TEST" == response["name"]
        assert "test_api1.gns3" == response["filename"]
        assert "opened" == response["status"]

    def test_get_project_by_id(self, gns3_server):
        response = gns3_server.get_project_by_id(CPROJECT["id"])
        assert "API_TEST" == response["name"]
        assert "test_api1.gns3" == response["filename"]
        assert "opened" == response["status"]

    def test_project_not_found(self, gns3_server):
        response = gns3_server.get_project_by_id("7777-4444-0000")
        assert "Project ID 7777-4444-0000 doesn't exist" == response["message"]
        assert 404 == response["status"]

    def test_get_nodes(self, gns3_server):
        response = gns3_server.get_nodes(project_id=CPROJECT["id"])
        for index, n in enumerate(
            [
                ("Ethernetswitch-1", "ethernet_switch"),
                ("IOU1", "iou"),
                ("IOU2", "iou"),
                ("vEOS", "qemu"),
                ("alpine-1", "docker"),
                ("Cloud-1", "cloud"),
            ]
        ):
            assert n[0] == response[index]["name"]
            assert n[1] == response[index]["node_type"]

    def test_get_node_by_id(self, gns3_server):
        response = gns3_server.get_node_by_id(
            project_id=CPROJECT["id"], node_id=CNODE["id"]
        )
        assert "alpine-1" == response["name"]
        assert "docker" == response["node_type"]
        assert 5005 == response["console"]

    def test_node_not_found(self, gns3_server):
        response = gns3_server.get_node_by_id(
            project_id=CPROJECT["id"], node_id="7777-4444-0000"
        )
        assert "Node ID 7777-4444-0000 doesn't exist" == response["message"]
        assert 404 == response["status"]

    def test_get_links(self, gns3_server):
        response = gns3_server.get_links(project_id=CPROJECT["id"])
        assert "ethernet" == response[0]["link_type"]

    def test_get_link_by_id(self, gns3_server):
        response = gns3_server.get_link_by_id(
            project_id=CPROJECT["id"], link_id=CLINK["id"]
        )
        assert "ethernet" == response["link_type"]
        assert CPROJECT["id"] == response["project_id"]
        assert response["suspend"] is False

    def test_link_not_found(self, gns3_server):
        response = gns3_server.get_link_by_id(
            project_id=CPROJECT["id"], link_id="7777-4444-0000"
        )
        assert "Link ID 7777-4444-0000 doesn't exist" == response["message"]
        assert 404 == response["status"]

    def test_create_project(self, gns3_server):
        response = gns3_server.create_project(name="API_TEST")
        assert "API_TEST" == response["name"]
        assert "opened" == response["status"]

    def test_create_duplicate_project(self, gns3_server):
        response = gns3_server.create_project(name="DUPLICATE")
        assert "Project 'DUPLICATE' already exists" == response["message"]
        assert 409 == response["status"]

    def test_delete_project(self, gns3_server):
        response = gns3_server.delete_project(project_id=CPROJECT["id"])
        assert response is None


@pytest.fixture(scope="class")
def api_test_link(gns3_server):
    link = Link(link_id=CLINK["id"], connector=gns3_server, project_id=CPROJECT["id"])
    link.get()
    return link


class TestLink:
    def test_instatiation(self):
        for index, link_data in enumerate(links_data()):
            assert links.LINKS_REPR[index] == repr(Link(**link_data))

    def test_get(self, api_test_link):
        assert api_test_link.link_type == "ethernet"
        assert api_test_link.filters == {}
        assert api_test_link.capturing is False
        assert api_test_link.suspend is False
        assert api_test_link.nodes[-1]["node_id"] == CNODE["id"]
        assert api_test_link.nodes[-1]["adapter_number"] == 0
        assert api_test_link.nodes[-1]["port_number"] == 0

    def test_create(self, gns3_server):
        _link_data = [
            {
                "adapter_number": 2,
                "port_number": 0,
                "node_id": "8283b923-df0e-4bc1-8199-be6fea40f500",
            },
            {"adapter_number": 0, "port_number": 0, "node_id": CNODE["id"]},
        ]
        link = Link(connector=gns3_server, project_id=CPROJECT["id"], nodes=_link_data)
        link.create()
        assert link.link_type == "ethernet"
        assert link.filters == {}
        assert link.capturing is False
        assert link.suspend is False
        assert link.nodes[-1]["node_id"] == CNODE["id"]

    def test_create_with_incomplete_node_data(self, gns3_server):
        _link_data = [{"adapter_number": 0, "port_number": 0, "node_id": CNODE["id"]}]
        link = Link(connector=gns3_server, project_id=CPROJECT["id"], nodes=_link_data)
        with pytest.raises(ValueError, match="400"):
            link.create()

    def test_create_with_invalid_nodes_id(self, gns3_server):
        _link_data = [
            {"adapter_number": 2, "port_number": 0, "node_id": CNODE["id"]},
            {"adapter_number": 0, "port_number": 0, "node_id": CNODE["id"]},
        ]
        link = Link(connector=gns3_server, project_id=CPROJECT["id"], nodes=_link_data)
        with pytest.raises(ValueError, match="409"):
            link.create()

    def test_delete(self, api_test_link):
        api_test_link.delete()
        assert api_test_link.project_id is None
        assert api_test_link.link_id is None


@pytest.fixture(scope="class")
def api_test_node(gns3_server):
    node = Node(name="alpine-1", connector=gns3_server, project_id=CPROJECT["id"])
    node.get()
    return node


class TestNode:
    def test_instatiation(self):
        for index, node_data in enumerate(nodes_data()):
            assert nodes.NODES_REPR[index] == repr(Node(**node_data))

    def test_get(self, api_test_node):
        assert "alpine-1" == api_test_node.name
        assert "started" == api_test_node.status
        assert "docker" == api_test_node.node_type
        assert "alpine:latest" == api_test_node.properties["image"]

    def test_get_links(self, api_test_node):
        api_test_node.get_links()
        assert "ethernet" == api_test_node.links[0].link_type
        assert 2 == api_test_node.links[0].nodes[0]["adapter_number"]
        assert 0 == api_test_node.links[0].nodes[0]["port_number"]

    def test_start(self, api_test_node):
        api_test_node.start()
        assert "alpine-1" == api_test_node.name
        assert "started" == api_test_node.status

    def test_stop(self, api_test_node):
        api_test_node.stop()
        assert "alpine-1" == api_test_node.name
        assert "stopped" == api_test_node.status

    def test_suspend(self, api_test_node):
        api_test_node.suspend()
        assert "alpine-1" == api_test_node.name
        assert "suspended" == api_test_node.status

    def test_reload(self, api_test_node):
        api_test_node.reload()
        assert "alpine-1" == api_test_node.name
        assert "started" == api_test_node.status

    def test_create(self, gns3_server):
        node = Node(
            name="alpine-1",
            node_type="docker",
            template=CTEMPLATE["name"],
            connector=gns3_server,
            project_id=CPROJECT["id"],
        )
        node.create()
        assert "alpine-1" == node.name
        assert "started" == node.status
        assert "docker" == node.node_type
        assert "alpine:latest" == node.properties["image"]

    def test_create_with_invalid_parameter_type(self, gns3_server):
        with pytest.raises(ValidationError):
            Node(
                name="alpine-1",
                node_type="docker",
                template=CTEMPLATE["name"],
                connector=gns3_server,
                project_id=CPROJECT["id"],
                compute_id=None,
            )

    def test_create_with_incomplete_parameters(self, gns3_server):
        node = Node(
            name="alpine-1",
            connector=gns3_server,
            project_id=CPROJECT["id"],
        )
        with pytest.raises(ValueError, match="Need to submit 'node_type'"):
            node.create()

    def test_delete(self, api_test_node):
        api_test_node.delete()
        assert api_test_node.project_id is None
        assert api_test_node.node_id is None
        assert api_test_node.name is None


@pytest.fixture(scope="class")
def api_test_project(gns3_server):
    project = Project(name="API_TEST", connector=gns3_server)
    project.get()
    return project


class TestProject:
    def test_instatiation(self):
        for index, project_data in enumerate(projects_data()):
            assert projects.PROJECTS_REPR[index] == repr(Project(**project_data))

    def test_create(self, gns3_server):
        api_test_project = Project(name="API_TEST", connector=gns3_server)
        api_test_project.create()
        assert "API_TEST" == api_test_project.name
        assert "opened" == api_test_project.status
        assert False is api_test_project.auto_close

    def test_delete(self, gns3_server):
        api_test_project = Project(name="API_TEST", connector=gns3_server)
        api_test_project.create()
        resp = api_test_project.delete()
        assert resp is None

    def test_get(self, api_test_project):
        assert "API_TEST" == api_test_project.name
        assert "opened" == api_test_project.status
        assert {
            "drawings": 0,
            "links": 4,
            "nodes": 6,
            "snapshots": 0,
        } == api_test_project.stats

    def test_update(self, api_test_project):
        api_test_project.update(filename="file_updated.gns3")
        assert "API_TEST" == api_test_project.name
        assert "opened" == api_test_project.status
        assert "file_updated.gns3" == api_test_project.filename

    def test_open(self, api_test_project):
        api_test_project.open()
        assert "API_TEST" == api_test_project.name
        assert "opened" == api_test_project.status

    def test_close(self, api_test_project):
        api_test_project.close()
        assert "API_TEST" == api_test_project.name
        assert "closed" == api_test_project.status

    def test_get_stats(self, api_test_project):
        api_test_project.get_stats()
        assert {
            "drawings": 0,
            "links": 4,
            "nodes": 6,
            "snapshots": 0,
        } == api_test_project.stats

    def test_get_nodes(self, api_test_project):
        api_test_project.get_nodes()
        for index, n in enumerate(
            [
                ("Ethernetswitch-1", "ethernet_switch"),
                ("IOU1", "iou"),
                ("IOU2", "iou"),
                ("vEOS", "qemu"),
                ("alpine-1", "docker"),
                ("Cloud-1", "cloud"),
            ]
        ):
            assert n[0] == api_test_project.nodes[index].name
            assert n[1] == api_test_project.nodes[index].node_type

    def test_get_links(self, api_test_project):
        api_test_project.get_links()
        assert "ethernet" == api_test_project.links[0].link_type

    # TODO: Need to make a way to dynamically change the status of the nodes to started
    # when the inner method `get_nodes` hits again the server REST endpoint
    @pytest.mark.skip
    def test_start_nodes(self, api_test_project):
        api_test_project.start_nodes()
        for node in api_test_project.nodes:
            assert "started" == node.status

    @pytest.mark.skip
    def test_stop_nodes(self, api_test_project):
        api_test_project.stop_nodes()
        for node in api_test_project.nodes:
            assert "stopped" == node.status

    @pytest.mark.skip
    def test_reload_nodes(self, api_test_project):
        api_test_project.reload_nodes()
        for node in api_test_project.nodes:
            assert "started" == node.status

    @pytest.mark.skip
    def test_suspend_nodes(self, api_test_project):
        api_test_project.suspend_nodes()
        for node in api_test_project.nodes:
            assert "suspended" == node.status

    def test_nodes_summary(self, api_test_project):
        nodes_summary = api_test_project.nodes_summary(is_print=False)
        assert str(nodes_summary) == (
            "[('Ethernetswitch-1', 'started', '5000', "
            "'da28e1c0-9465-4f7c-b42c-49b2f4e1c64d'), ('IOU1', 'started', '5001', "
            "'de23a89a-aa1f-446a-a950-31d4bf98653c'), ('IOU2', 'started', '5002', "
            "'0d10d697-ef8d-40af-a4f3-fafe71f5458b'), ('vEOS', 'started', '5003', "
            "'8283b923-df0e-4bc1-8199-be6fea40f500'), ('alpine-1', 'started', '5005', "
            "'ef503c45-e998-499d-88fc-2765614b313e'), ('Cloud-1', 'started', None, "
            "'cde85a31-c97f-4551-9596-a3ed12c08498')]"
        )

    def test_links_summary(self, api_test_project):
        api_test_project.get_links()
        links_summary = api_test_project.links_summary(is_print=False)
        assert str(links_summary) == (
            "[('IOU1', 'Ethernet0/0', 'Ethernetswitch-1', 'Ethernet1'), ('IOU1', "
            "'Ethernet1/0', 'IOU2', 'Ethernet1/0'), ('vEOS', 'Management1', "
            "'Ethernetswitch-1', 'Ethernet0'), ('vEOS', 'Ethernet1', 'alpine-1', "
            "'eth0'), ('Cloud-1', 'eth1', 'Ethernetswitch-1', 'Ethernet7')]"
        )

    def test_get_node_by_name(self, api_test_project):
        switch = api_test_project.get_node(name="IOU1")
        assert "IOU1" == switch.name
        assert "started" == switch.status
        assert "5001" == switch.console

    def test_get_node_by_id(self, api_test_project):
        host = api_test_project.get_node(node_id=CNODE["id"])
        assert "alpine-1" == host.name
        assert "started" == host.status
        assert "5005" == host.console

    # TODO: `get_link` is dependent on the nodes information of the links
    @pytest.mark.skip
    def test_get_link_by_id(self, api_test_project):
        link = api_test_project.get_link(link_id=CLINK["id"])
        assert "ethernet" == link.link_type