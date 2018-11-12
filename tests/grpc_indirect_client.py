# -*- coding: utf-8 -*-
import sys
import threading
from importlib import import_module

import grpc
from grpc._cython.cygrpc import CompressionAlgorithm, CompressionLevel

from nameko_grpc.exceptions import GrpcError

from helpers import FifoPipe, SafeSender, receive, send


def call(fifo_in, fifo_out, method, kwargs):
    request = receive(fifo_in)
    try:
        response = method(request, **kwargs)
    except grpc.RpcError as exc:
        state = exc._state
        response = GrpcError(state.code, state.details, state.debug_error_string)

    response = SafeSender.wrap(response)
    send(fifo_out, response)


if __name__ == "__main__":

    port = sys.argv[1]

    spec_path = sys.argv[2]
    sys.path.append(spec_path)

    proto_name = sys.argv[3]
    service_name = sys.argv[4]

    compression_algorithm = sys.argv[5]
    compression_level = sys.argv[6]

    grpc_module = import_module("{}_pb2_grpc".format(proto_name))
    stub_cls = getattr(grpc_module, "{}Stub".format(service_name))

    command_fifo_path = sys.argv[7]
    command_fifo = FifoPipe.wrap(command_fifo_path)

    channel_options = [
        (
            "grpc.default_compression_algorithm",
            getattr(CompressionAlgorithm, compression_algorithm),
        ),
        (
            "grpc.default_compression_level",
            getattr(CompressionLevel, compression_level),
        ),
    ]

    channel = grpc.insecure_channel(
        "127.0.0.1:{}".format(port), options=channel_options
    )
    stub = stub_cls(channel)

    while True:
        config = receive(command_fifo)
        if config is None:
            break

        in_fifo_path = config.in_fifo
        in_fifo = FifoPipe.wrap(in_fifo_path)

        out_fifo_path = config.out_fifo
        out_fifo = FifoPipe.wrap(out_fifo_path)

        method = getattr(stub, config.method_name)

        compression = config.kwargs.pop("compression", None)
        if compression:
            config.kwargs["metadata"] = list(config.kwargs.get("metadata", [])) + [
                ("grpc-internal-encoding-request", compression)
            ]

        thread = threading.Thread(
            target=call,
            name=config.method_name,
            args=(in_fifo, out_fifo, method, config.kwargs),
        )
        thread.start()
