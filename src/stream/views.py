import mimetypes
import os
import pickle
import re
from wsgiref.util import FileWrapper

from django.http.response import StreamingHttpResponse
from django.shortcuts import render


def gen_message(msg):
    return 'data: {}'.format(msg)


def iterator():
    for i in range(10000):
        yield gen_message('iteration ' + str(i))


def test_stream(request):
    stream = iterator()
    response = StreamingHttpResponse(stream, status=200, content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response


def home(request):
    import pickle
    import datetime

    data_boxes = pickle.load(open('core/boxes_per_cam_per_10frames.pickle', 'rb'))

    print(str(datetime.timedelta(seconds=len(data_boxes[0]) * 10 / 25)))
    print(str(datetime.timedelta(seconds=len(data_boxes[1]) * 10 / 25)))

    # cast tuples to lists
    for i in range(len(data_boxes)):
        for j in range(len(data_boxes[i])):
            for k in range(len(data_boxes[i][j])):
                data_boxes[i][j][k] = list(data_boxes[i][j][k])

    data_boxes[0].append([])
    data_boxes[1].append([])
    print(data_boxes)

    data_clusters = pickle.load(open('core/classes_per_cam.pickle', 'rb'))
    data_clusters = [data_clusters[0][::10], data_clusters[1][::10]]
    data_clusters[0].append([])
    data_clusters[1].append([])
    print(data_clusters)

    return render(request, 'index.html', {'data_boxes': data_boxes, 'data_clusters': data_clusters})


range_re = re.compile(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', re.I)


class RangeFileWrapper(object):
    def __init__(self, filelike, blksize=8192, offset=0, length=None):
        self.filelike = filelike
        self.filelike.seek(offset, os.SEEK_SET)
        self.remaining = length
        self.blksize = blksize

    def close(self):
        if hasattr(self.filelike, 'close'):
            self.filelike.close()

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining is None:
            # If remaining is None, we're reading the entire file.
            data = self.filelike.read(self.blksize)
            if data:
                return data
            raise StopIteration()
        else:
            if self.remaining <= 0:
                raise StopIteration()
            data = self.filelike.read(min(self.remaining, self.blksize))
            if not data:
                raise StopIteration()
            self.remaining -= len(data)
            return data


def stream_video(request):
    videos = ['campus4-c0.mp4', 'campus4-c1.mp4']
    path = 'core/videos/' + videos[int(request.GET['n'])]
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = range_re.match(range_header)
    size = os.path.getsize(path)
    content_type, encoding = mimetypes.guess_type(path)
    content_type = content_type or 'application/octet-stream'
    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else size - 1
        if last_byte >= size:
            last_byte = size - 1
        length = last_byte - first_byte + 1
        resp = StreamingHttpResponse(RangeFileWrapper(open(path, 'rb'), offset=first_byte, length=length), status=206,
                                     content_type=content_type)
        resp['Content-Length'] = str(length)
        resp['Content-Range'] = 'bytes %s-%s/%s' % (first_byte, last_byte, size)
    else:
        resp = StreamingHttpResponse(FileWrapper(open(path, 'rb')), content_type=content_type)
        resp['Content-Length'] = str(size)
    resp['Accept-Ranges'] = 'bytes'
    return resp
