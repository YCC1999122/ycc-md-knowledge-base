"""First-run model download + smoke test for semantic embeddings (dev machine)."""
import os
import sys

sys.path.insert(0, ".")
os.environ.pop("HF_HUB_OFFLINE", None)            # allow download on dev machine
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # CN mirror

from app.core import semantic  # noqa: E402

print("cache dir:", semantic.model_dir())
model = semantic._get_model()
if model is None:
    sys.exit("model load failed")
print("model ready")

pairs = [
    ("护林员每日巡护记录：上午沿东线巡查，发现火灾隐患一处，已上报处理。", "护林员巡山日志"),
    ("园区出入管理办法：外来人员须登记身份证，并由被访部门派人接待。", "门禁出入制度"),
]
vecs = semantic.embed_texts([p[0] for p in pairs])
import numpy as np
a, b = np.asarray(vecs[0]), np.asarray(vecs[1])
print("dim:", len(vecs[0]))
print("sim(巡护日志, 巡山日志) =", round(float(a @ b), 4))
q = np.asarray(semantic.embed_query("森林防火巡查"))
print("sim(query 防火巡查, 巡护日志) =", round(float(q @ a), 4))
print("sim(query 防火巡查, 出入制度) =", round(float(q @ b), 4))
print("MODEL DOWNLOAD & SMOKE OK")
