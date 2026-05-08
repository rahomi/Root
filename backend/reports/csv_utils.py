# apps/reports/csv_utils.py
# ---------------------------------------------------------------------------
# Streaming CSV helpers — uses Django's StreamingHttpResponse so large
# exports never buffer the entire dataset in memory.
# ---------------------------------------------------------------------------

import csv
import io
from django.http import StreamingHttpResponse


class _EchoBuffer:
    """A write-only buffer that returns the value written (for streaming)."""
    def write(self, value):
        return value


def streaming_csv_response(rows_generator, filename: str) -> StreamingHttpResponse:
    """
    Build a StreamingHttpResponse that streams CSV rows one at a time.

    Args:
        rows_generator: An iterable of lists (first row = header).
        filename:       The suggested download filename.

    Usage:
        def _rows():
            yield ["col1", "col2"]
            for obj in qs.iterator():
                yield [obj.field1, obj.field2]

        return streaming_csv_response(_rows(), "export.csv")
    """
    buffer  = _EchoBuffer()
    writer  = csv.writer(buffer)

    def stream():
        for row in rows_generator:
            yield writer.writerow(row)

    response = StreamingHttpResponse(
        streaming_content=stream(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response