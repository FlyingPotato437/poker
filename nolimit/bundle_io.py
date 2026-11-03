"""Write/read table bundles with numpy (offline side). runtime.read_bundle is the stdlib reader."""
import json
import struct
import zlib

import numpy as np

from .runtime import BUNDLE_MAGIC

_ALLOWED = {"float32", "int32", "int16", "int8", "uint8"}


def write_bundle(path, meta, arrays, level=9):
    header = {"meta": meta, "arrays": {}}
    chunks = []
    offset = 0
    for name, arr in arrays.items():
        arr = np.ascontiguousarray(arr)
        if arr.dtype.name not in _ALLOWED:
            raise TypeError(f"{name}: dtype {arr.dtype} not allowed")
        raw = arr.astype(arr.dtype.newbyteorder("<")).tobytes()
        header["arrays"][name] = {"dtype": arr.dtype.name, "shape": list(arr.shape),
                                  "offset": offset, "nbytes": len(raw)}
        chunks.append(raw)
        offset += len(raw)
    hdr = json.dumps(header).encode()
    blob = BUNDLE_MAGIC + struct.pack("<I", len(hdr)) + hdr + zlib.compress(b"".join(chunks), level)
    with open(path, "wb") as fh:
        fh.write(blob)
    return len(blob)


def read_bundle_np(path):
    with open(path, "rb") as fh:
        data = fh.read()
    (hlen,) = struct.unpack("<I", data[4:8])
    header = json.loads(data[8:8 + hlen].decode())
    payload = zlib.decompress(data[8 + hlen:])
    arrays = {}
    for name, info in header["arrays"].items():
        a = np.frombuffer(payload[info["offset"]:info["offset"] + info["nbytes"]],
                          dtype=np.dtype(info["dtype"]).newbyteorder("<"))
        arrays[name] = a.reshape(info["shape"]).copy()
    return header["meta"], arrays
