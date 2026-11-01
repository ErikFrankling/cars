#!/usr/bin/env python3
"""Encode real ETSI ITS PDUs with the ASN.1 published on forge.etsi.org and report UPER bytes.

Usage: nix-shell -p 'python3.withPackages(p:[p.asn1tools])' --run \
  'python3 -I research/truth/scripts/v2x_msgsizes.py <asn1-dir> <out.json>'
UPER sizes depend on which optional fields are present and list lengths, not on values,
so fields take their minimum legal value unless a builder overrides them.
"""
import asn1tools, json, sys
from asn1tools.codecs import per, uper

A = sys.argv[1].rstrip("/") + "/"
CDD = A + "cdd_ts102894_2/ETSI-ITS-CDD.asn"
DSRC = [A + "is_ts103301/" + f for f in ["DSRC.asn", "DSRC-region.asn", "DSRC-addgrp-C.asn"]]


def fill(t, want=None, path=""):
    want = want or {}
    k = type(t).__name__
    if k in ("Sequence", "Set"):
        out = {}
        for m in t.root_members:
            p = path + "/" + m.name
            if (not m.optional and m.default is None) or any(p.endswith(w) for w in want):
                out[m.name] = fill(m, want, p)
        return out
    if k == "Choice":
        members = list(t.root_index_to_member.values())
        for n in list(want):
            for m in members:
                if (path + "/" + m.name).endswith(n):
                    return (m.name, fill(m, want, path + "/" + m.name))
        m = members[0]
        return (m.name, fill(m, want, path + "/" + m.name))
    if k in ("SequenceOf", "SetOf"):
        n = t.minimum if t.minimum is not None else 0
        for w, v in want.items():
            if path.endswith(w) and isinstance(v, int):
                n = v
        return [fill(t.element_type, want, path + "[]") for _ in range(n)]
    if k == "Integer":
        return t.minimum if t.minimum not in (None, "MIN") else 0
    if k == "Boolean":
        return False
    if k == "Null":
        return None
    if k == "Enumerated":
        return list(t.root_data_to_index.keys())[0]
    if k == "BitString":
        n = t.minimum if t.minimum else 8
        return (b"\0" * ((n + 7) // 8), n)
    if k == "OctetString":
        n = t.minimum if t.minimum else 1
        return b"\0" * n
    if k in ("IA5String", "VisibleString", "UTF8String", "NumericString", "PrintableString", "BMPString", "GeneralString"):
        return "a" * (t.minimum or 1)
    if k == "OpenType":
        return b""
    raise SystemExit(f"unhandled {k} at {path}")


def size(s, name, want):
    d = s.types[name]
    v = fill(d.type, want, "")
    return len(s.encode(name, v, check_constraints=False)), v


cam = asn1tools.compile_files([A + "cam_ts103900/CAM-PDU-Descriptions.asn", CDD], "uper")
out = {}
want_hf = {"highFrequencyContainer": True, "basicVehicleContainerHighFrequency": True}
out["CAM high-frequency only"] = size(cam, "CAM", want_hf)[0]
for n in (0, 5, 10, 15, 23, 40):
    out[f"CAM with low-frequency, {n} path history points"] = size(
        cam, "CAM", {**want_hf, "lowFrequencyContainer": True, "basicVehicleContainerLowFrequency": True, "pathHistory": n}
    )[0]

# Path prediction is in an extension container. Encode the container alone, then wrap it.
for n, opts in ((5, ""), (8, ""), (10, ""), (16, ""), (5, "conf"), (10, "conf"), (16, "conf"), (30, ""), (40, "")):
    w = {"pathPredictedList": 1, "pathPredicted": n, "pathDeltaTime": True}
    if opts:
        w["horizontalPositionConfidence"] = True
    b = size(cam, "PathPredictionContainer", w)[0]
    # WrappedExtensionContainers: extension bit, list count, containerId, open type length + data (TS 103 900 Annex A)
    out[f"PathPredictionContainer, {n} points with time{' and position confidence' if opts else ''}: inner"] = b
    out[f"PathPredictionContainer, {n} points with time{' and position confidence' if opts else ''}: wrapped"] = b + (2 if b < 128 else 3) + 2

out["CDD PathPointPredicted, time only"] = size(cam, "PathPointPredicted", {"pathDeltaTime": True})[0]
out["VehicleMovementControlContainer"] = size(cam, "VehicleMovementControlContainer", {})[0]

spat = asn1tools.compile_files([A + "is_ts103301/SPATEM-PDU-Descriptions.asn"] + DSRC + [CDD], "uper")
for g in (4, 8, 12, 16, 24, 32):
    for tag, tim in (("minEndTime only", {"timing": True}),
                     ("min, max, likely, confidence", {"timing": True, "maxEndTime": True, "likelyTime": True, "confidence": True})):
        out[f"SPATEM, {g} signal groups, {tag}"] = size(spat, "SPATEM", {"states": g, "state-time-speed": 1, "moy": True, "timeStamp": True, **tim})[0]

mp = asn1tools.compile_files([A + "is_ts103301/MAPEM-PDU-Descriptions.asn"] + DSRC + [CDD], "uper")
for lanes, nodes, conns in ((8, 4, 2), (12, 5, 2), (16, 5, 3), (24, 6, 3), (32, 8, 3)):
    w = {"intersections": 1, "laneSet": lanes, "nodes": nodes, "connectsTo": conns, "signalGroup": True, "laneWidth": True, "ingressApproach": True, "speedLimits": 1}
    out[f"MAPEM, {lanes} lanes, {nodes} nodes each, {conns} connections each"] = size(mp, "MAPEM", w)[0]

sr = asn1tools.compile_files([A + "is_ts103301/SREM-PDU-Descriptions.asn"] + DSRC + [CDD], "uper")
out["SREM, one request"] = size(sr, "SREM", {"requests": 1, "minute": True, "second": True, "duration": True, "outBoundLane": True, "/type": True})[0]
ss = asn1tools.compile_files([A + "is_ts103301/SSEM-PDU-Descriptions.asn"] + DSRC + [CDD], "uper")
out["SSEM, one status"] = size(ss, "SSEM", {"status": 1, "sigStatus": 1, "requester": True, "minute": True, "second": True, "duration": True})[0]
out["SSEM, 8 statuses"] = size(ss, "SSEM", {"status": 1, "sigStatus": 8, "requester": True, "minute": True, "second": True, "duration": True})[0]

de = asn1tools.compile_files([A + "denm_ts103831/DENM-PDU-Descriptions.asn", CDD], "uper")
out["DENM, management and situation"] = size(de, "DENM", {"situation": True})[0]

vam = asn1tools.compile_files([A + "vam-ts103300_3/VAM-PDU-Descriptions.asn", CDD], "uper")
out["VAM, mandatory only"] = size(vam, "VAM", {})[0]

cpmf = [A + "cpm_ts103324/" + f for f in ["CPM-PDU-Descriptions.asn", "CPM-OriginatingStationContainers.asn", "CPM-SensorInformationContainer.asn", "CPM-PerceptionRegionContainer.asn", "CPM-PerceivedObjectContainer.asn"]]
cpm = asn1tools.compile_files(cpmf + [CDD], "uper")
base = size(cpm, "OriginatingVehicleContainer", {})[0] + size(cpm, "ManagementContainer", {})[0] + 6 + 6
out["CPM header, management and originating vehicle containers, approx"] = base
for n in (1, 5, 10, 20):
    o = {"perceivedObjects": n}
    out[f"CPM perceived object container, {n} objects, position only"] = size(cpm, "PerceivedObjectContainer", o)[0]
    o = {**o, "velocity": True, "acceleration": True, "angles": True, "objectDimensionX": True, "objectDimensionY": True, "classification": 1, "objectId": True, "objectAge": True}
    out[f"CPM perceived object container, {n} objects, kinematics, size, class"] = size(cpm, "PerceivedObjectContainer", o)[0]

json.dump(out, open(sys.argv[2], "w"), indent=1)
for k, v in out.items():
    print(f"{v:6d} B  {k}")
