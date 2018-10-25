# -*- coding: utf-8 -*-
import random
import string

import pytest
from grpc import StatusCode
from mock import Mock
from nameko.testing.services import dummy
from nameko.testing.utils import get_extension

from nameko_grpc.client import Client
from nameko_grpc.constants import Cardinality
from nameko_grpc.dependency_provider import GrpcProxy
from nameko_grpc.exceptions import GrpcError
from nameko_grpc.inspection import Inspector


@pytest.fixture
def grpc_server(start_grpc_server):
    return start_grpc_server("example")


@pytest.fixture
def grpc_client(start_grpc_client):
    return start_grpc_client("example")


@pytest.fixture
def nameko_server(start_nameko_server):
    return start_nameko_server("example")


@pytest.fixture
def nameko_client(start_nameko_client):
    return start_nameko_client("example")


class TestInspection:
    @pytest.fixture
    def stubs(self, compile_stubs):
        return compile_stubs("example")

    @pytest.fixture
    def protobufs(self, compile_protobufs):
        return compile_protobufs("example")

    @pytest.fixture
    def inspector(self, stubs):
        return Inspector(stubs.exampleStub)

    def test_service_name(self, inspector):
        assert inspector.service_name == "nameko.example"

    def test_path_for_method(self, inspector):
        assert inspector.path_for_method("unary_unary") == "/nameko.example/unary_unary"
        assert (
            inspector.path_for_method("unary_stream") == "/nameko.example/unary_stream"
        )
        assert (
            inspector.path_for_method("stream_stream")
            == "/nameko.example/stream_stream"
        )
        assert (
            inspector.path_for_method("stream_unary") == "/nameko.example/stream_unary"
        )

    def test_input_type_for_method(self, inspector, protobufs):
        assert (
            inspector.input_type_for_method("unary_unary") == protobufs.ExampleRequest
        )

    def test_output_type_for_method(self, inspector, protobufs):
        assert inspector.output_type_for_method("unary_unary") == protobufs.ExampleReply

    def test_cardinality_for_method(self, inspector):
        insp = inspector
        assert insp.cardinality_for_method("unary_unary") == Cardinality.UNARY_UNARY
        assert insp.cardinality_for_method("unary_stream") == Cardinality.UNARY_STREAM
        assert insp.cardinality_for_method("stream_unary") == Cardinality.STREAM_UNARY
        assert insp.cardinality_for_method("stream_stream") == Cardinality.STREAM_STREAM


@pytest.fixture(params=["grpc_server", "nameko_server"])
def server(request):
    if "grpc" in request.param:
        if request.config.option.server not in ("grpc", "all"):
            pytest.skip("grpc server not requested")
        request.getfixturevalue("grpc_server")
    elif "nameko" in request.param:
        if request.config.option.server not in ("nameko", "all"):
            pytest.skip("nameko server not requested")
        request.getfixturevalue("nameko_server")


@pytest.fixture(params=["grpc_client", "nameko_client"])
def client(request, server):
    if "grpc" in request.param:
        if request.config.option.client not in ("grpc", "all"):
            pytest.skip("grpc client not requested")
        return request.getfixturevalue("grpc_client")
    elif "nameko" in request.param:
        if request.config.option.client not in ("nameko", "all"):
            pytest.skip("nameko client not requested")
        return request.getfixturevalue("nameko_client")


class TestStandard:
    @pytest.fixture
    def stubs(self, compile_stubs):
        return compile_stubs("example")

    @pytest.fixture
    def protobufs(self, compile_protobufs):
        return compile_protobufs("example")

    def test_unary_unary(self, client, protobufs):
        response = client.unary_unary(protobufs.ExampleRequest(value="A"))
        assert response.message == "A"

    def test_unary_stream(self, client, protobufs):
        responses = client.unary_stream(protobufs.ExampleRequest(value="A"))
        assert [(response.message, response.seqno) for response in responses] == [
            ("A", 1),
            ("A", 2),
        ]

    def test_stream_unary(self, client, protobufs):
        def generate_requests():
            for value in ["A", "B"]:
                yield protobufs.ExampleRequest(value=value)

        response = client.stream_unary(generate_requests())
        assert response.message == "A,B"

    def test_stream_stream(self, client, protobufs):
        def generate_requests():
            for value in ["A", "B"]:
                yield protobufs.ExampleRequest(value=value)

        responses = client.stream_stream(generate_requests())
        assert [(response.message, response.seqno) for response in responses] == [
            ("A", 1),
            ("B", 2),
        ]


class TestLarge:
    @pytest.fixture
    def stubs(self, compile_stubs):
        return compile_stubs("example")

    @pytest.fixture
    def protobufs(self, compile_protobufs):
        return compile_protobufs("example")

    def test_large_request(self, client, protobufs):
        response = client.unary_unary(
            protobufs.ExampleRequest(value="A", blob="B" * 20000)
        )
        assert response.message == "A"

    def test_large_response(self, client, protobufs):
        multiplier = 20000
        response = client.unary_unary(
            protobufs.ExampleRequest(value="A", multiplier=multiplier)
        )
        assert response.message == "A" * multiplier


class TestFuture:
    @pytest.fixture
    def stubs(self, compile_stubs):
        return compile_stubs("example")

    @pytest.fixture
    def protobufs(self, compile_protobufs):
        return compile_protobufs("example")

    def test_unary_unary(self, client, protobufs):
        response_future = client.unary_unary.future(protobufs.ExampleRequest(value="A"))
        response = response_future.result()
        assert response.message == "A"

    def test_unary_stream(self, client, protobufs):
        responses_future = client.unary_stream.future(
            protobufs.ExampleRequest(value="A")
        )
        responses = responses_future.result()
        assert [(response.message, response.seqno) for response in responses] == [
            ("A", 1),
            ("A", 2),
        ]

    def test_stream_unary(self, client, protobufs):
        def generate_requests():
            for value in ["A", "B"]:
                yield protobufs.ExampleRequest(value=value)

        response_future = client.stream_unary.future(generate_requests())
        response = response_future.result()
        assert response.message == "A,B"

    def test_stream_stream(self, client, protobufs):
        def generate_requests():
            for value in ["A", "B"]:
                yield protobufs.ExampleRequest(value=value)

        responses_future = client.stream_stream.future(generate_requests())
        responses = responses_future.result()
        assert [(response.message, response.seqno) for response in responses] == [
            ("A", 1),
            ("B", 2),
        ]


class TestConcurrency:
    # XXX how to assert both are in flight at the same time?
    @pytest.fixture
    def stubs(self, compile_stubs):
        return compile_stubs("example")

    @pytest.fixture
    def protobufs(self, compile_protobufs):
        return compile_protobufs("example")

    def test_unary_unary(self, client, protobufs):
        response_a_future = client.unary_unary.future(
            protobufs.ExampleRequest(value="A")
        )
        response_b_future = client.unary_unary.future(
            protobufs.ExampleRequest(value="B")
        )
        response_a = response_a_future.result()
        response_b = response_b_future.result()
        assert response_a.message == "A"
        assert response_b.message == "B"

    def test_unary_stream(self, client, protobufs):
        responses_a_future = client.unary_stream.future(
            protobufs.ExampleRequest(value="A")
        )
        responses_b_future = client.unary_stream.future(
            protobufs.ExampleRequest(value="B")
        )
        responses_a = responses_a_future.result()
        responses_b = responses_b_future.result()
        # TODO add random delays and generator consumer that grabs whatever comes first
        # then verify streams are interleaved
        assert [(response.message, response.seqno) for response in responses_a] == [
            ("A", 1),
            ("A", 2),
        ]
        assert [(response.message, response.seqno) for response in responses_b] == [
            ("B", 1),
            ("B", 2),
        ]

    def test_stream_unary(self, client, protobufs):
        def generate_requests(values):
            for value in values:
                yield protobufs.ExampleRequest(value=value)

        # XXX any way to verify that the input streams were interleaved?
        response_1_future = client.stream_unary.future(generate_requests("AB"))
        response_2_future = client.stream_unary.future(generate_requests("XY"))
        response_1 = response_1_future.result()
        response_2 = response_2_future.result()
        assert response_1.message == "A,B"
        assert response_2.message == "X,Y"

    def test_stream_stream(self, client, protobufs):
        def generate_requests(values):
            for value in values:
                yield protobufs.ExampleRequest(value=value)

        # TODO add random delays and generator consumer that grabs whatever comes first
        # then verify streams are interleaved
        # XXX any way to verify that the input streams were interleaved? perhaos track
        # the order the generators are pulled?
        responses_1_future = client.stream_stream.future(generate_requests("AB"))
        responses_2_future = client.stream_stream.future(generate_requests("XY"))
        responses_1 = responses_1_future.result()
        responses_2 = responses_2_future.result()
        assert [(response.message, response.seqno) for response in responses_1] == [
            ("A", 1),
            ("B", 2),
        ]
        assert [(response.message, response.seqno) for response in responses_2] == [
            ("X", 1),
            ("Y", 2),
        ]


class TestDependencyProvider:
    @pytest.fixture
    def stubs(self, compile_stubs):
        return compile_stubs("example")

    @pytest.fixture
    def protobufs(self, compile_protobufs):
        return compile_protobufs("example")

    @pytest.fixture
    def client(self, container_factory, stubs, server):
        class Service:
            name = "caller"

            example_grpc = GrpcProxy("//127.0.0.1", stubs.exampleStub)

            @dummy
            def call(self):
                pass

        container = container_factory(Service, {})
        container.start()

        grpc_proxy = get_extension(container, GrpcProxy)
        return grpc_proxy.get_dependency(Mock())

    def test_unary_unary(self, client, protobufs):
        response = client.unary_unary(protobufs.ExampleRequest(value="A"))
        assert response.message == "A"

    def test_unary_stream(self, client, protobufs):
        responses = client.unary_stream(protobufs.ExampleRequest(value="A"))
        assert [(response.message, response.seqno) for response in responses] == [
            ("A", 1),
            ("A", 2),
        ]

    def test_stream_unary(self, client, protobufs):
        def generate_requests():
            for value in ["A", "B"]:
                yield protobufs.ExampleRequest(value=value)

        response = client.stream_unary(generate_requests())
        assert response.message == "A,B"

    def test_stream_stream(self, client, protobufs):
        def generate_requests():
            for value in ["A", "B"]:
                yield protobufs.ExampleRequest(value=value)

        responses = client.stream_stream(generate_requests())
        assert [(response.message, response.seqno) for response in responses] == [
            ("A", 1),
            ("B", 2),
        ]


class TestMultipleClients:
    @pytest.fixture
    def stubs(self, compile_stubs):
        return compile_stubs("example")

    @pytest.fixture
    def protobufs(self, compile_protobufs):
        return compile_protobufs("example")

    # XXX
    @pytest.fixture
    def client_factory(self, stubs, server):
        clients = []

        def make():
            client = Client("//127.0.0.1", stubs.exampleStub)
            clients.append(client)
            return client.start()

        yield make

        for client in clients:
            client.stop()

    def test_unary_unary(self, client_factory, protobufs):

        futures = []
        number_of_clients = 10

        for index in range(number_of_clients):
            client = client_factory()
            response_future = client.unary_unary.future(
                protobufs.ExampleRequest(value=string.ascii_uppercase[index])
            )
            futures.append(response_future)

        for index, future in enumerate(futures):
            response = future.result()
            assert response.message == string.ascii_uppercase[index]

    def test_unary_stream(self, client_factory, protobufs):

        futures = []
        number_of_clients = 10

        for index in range(number_of_clients):
            client = client_factory()
            responses_future = client.unary_stream.future(
                protobufs.ExampleRequest(value=string.ascii_uppercase[index])
            )
            futures.append(responses_future)

        for index, future in enumerate(futures):
            responses = future.result()
            assert [(response.message, response.seqno) for response in responses] == [
                (string.ascii_uppercase[index], 1),
                (string.ascii_uppercase[index], 2),
            ]

    def test_stream_unary(self, client_factory, protobufs):

        number_of_clients = 10

        def shuffled(string):
            chars = list(string)
            random.shuffle(chars)
            return chars

        streams = [shuffled(string.ascii_uppercase) for _ in range(number_of_clients)]

        def generate_requests(values):
            for value in values:
                yield protobufs.ExampleRequest(value=value)

        futures = []

        for index in range(number_of_clients):
            client = client_factory()
            response_future = client.stream_unary.future(
                generate_requests(streams[index])
            )
            futures.append(response_future)

        for index, future in enumerate(futures):
            response = future.result()
            assert response.message == ",".join(streams[index])

    def test_stream_stream(self, client_factory, protobufs):

        number_of_clients = 10

        def shuffled(string):
            chars = list(string)
            random.shuffle(chars)
            return chars

        streams = [shuffled(string.ascii_uppercase) for _ in range(number_of_clients)]

        def generate_requests(values):
            for value in values:
                yield protobufs.ExampleRequest(value=value)

        futures = []

        for index in range(number_of_clients):
            client = client_factory()
            responses_future = client.stream_stream.future(
                generate_requests(streams[index])
            )
            futures.append(responses_future)

        for index, future in enumerate(futures):
            responses = future.result()

            expected = [(char, idx + 1) for idx, char in enumerate(streams[index])]
            received = [(response.message, response.seqno) for response in responses]

            assert received == expected


class TestMethodNotFound:
    @pytest.fixture
    def grpc_server(self, start_grpc_server, protobufs):
        return start_grpc_server("echo", proto_name="echo_server")

    @pytest.fixture
    def nameko_server(self, start_nameko_server, protobufs):
        return start_nameko_server("echo", proto_name="echo_server")

    @pytest.fixture
    def grpc_client(self, start_grpc_client, protobufs):
        return start_grpc_client("echo", proto_name="echo_client")

    @pytest.fixture
    def nameko_client(self, start_nameko_client, protobufs):
        return start_nameko_client("echo", proto_name="echo_client")

    @pytest.fixture
    def protobufs(self, compile_proto, spec_dir):
        protobufs, _ = compile_proto("echo")
        return protobufs

    def test_method_not_found(self, client, protobufs):
        response = client.foo(protobufs.EchoRequest(value="hello"))
        assert response.message == "hello"

        with pytest.raises(GrpcError) as error:
            client.bar(protobufs.EchoRequest(value="hello"))
        assert error.value.status == StatusCode.UNIMPLEMENTED
        assert error.value.details == "Method not found!"


# class TestTimeouts:
#     pass
