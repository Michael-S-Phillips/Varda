"""``python -m varda_torch_worker JOBDIR`` or ``--probe``; see ``protocol``.
A job is a classifier (``job``) or, with ``"task": "match"``, a matcher
(``matching``)."""

from __future__ import annotations

import json
import sys
import traceback


def _say(message: dict) -> None:
    print(json.dumps(message), flush=True)


def main(argv: list[str]) -> int:
    try:
        import torch

        from varda_torch_worker import models

        if argv == ["--probe"]:
            _say({"torch": torch.__version__, "device": models.device().type})
            return 0
        if len(argv) != 1:
            raise ValueError("usage: python -m varda_torch_worker JOBDIR | --probe")

        from varda_torch_worker import job, protocol

        def progress(fraction: float, message: str) -> None:
            _say({"progress": round(fraction, 4), "message": message})

        if protocol.jobTask(argv[0]).get("task") == "match":
            from varda_torch_worker.matching import METHODS

            reference, moving, method = protocol.readMatchJob(argv[0])
            protocol.writeMatches(argv[0], METHODS[method](reference, moving, progress))
            return 0
        arrays, classes, spec = protocol.readJob(argv[0])
        probabilities, info = job.trainAndClassify(
            arrays["cube"],
            arrays["valid"],
            arrays["rows"],
            arrays["cols"],
            arrays["labels"],
            classes,
            spec,
            progress,
        )
        protocol.writeResult(argv[0], probabilities, info)
        return 0
    except Exception as error:  # report every failure to Varda, then exit 1
        _say(
            {
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(),
            }
        )
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
