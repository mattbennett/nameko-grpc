# -*- coding: utf-8 -*-
import time

from helpers import instrumented

import example_pb2_grpc
from example_pb2 import ExampleReply


# TODO move stash to context once applciation headers are implemented
# TODO move compression to context once applciation headers are implemented


class example(example_pb2_grpc.exampleServicer):
    @instrumented
    def unary_unary(self, request, context):
        if request.delay:
            time.sleep(request.delay / 1000)
        message = request.value * (request.multiplier or 1)
        return ExampleReply(message=message, stash=request.stash)

    @instrumented
    def unary_stream(self, request, context):
        message = request.value * (request.multiplier or 1)
        for i in range(request.response_count):
            if request.delay:
                time.sleep(request.delay / 1000)
            yield ExampleReply(message=message, seqno=i + 1, stash=request.stash)

    @instrumented
    def stream_unary(self, request, context):
        messages = []
        for index, req in enumerate(request):
            if req.delay:
                time.sleep(req.delay / 1000)
            message = req.value * (req.multiplier or 1)
            messages.append(message)

        return ExampleReply(message=",".join(messages), stash=req.stash)

    @instrumented
    def stream_stream(self, request, context):
        for index, req in enumerate(request):
            if req.delay:
                time.sleep(req.delay / 1000)
            message = req.value * (req.multiplier or 1)
            yield ExampleReply(message=message, seqno=index + 1, stash=req.stash)
