"""``python -m varda_torch_worker JOBDIR`` or ``--probe``; see ``protocol``."""

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

        arrays, classes, spec = protocol.readJob(argv[0])
        probabilities, finalLoss = job.trainAndClassify(
            arrays["cube"],
            arrays["valid"],
            arrays["rows"],
            arrays["cols"],
            arrays["labels"],
            classes,
            spec,
            lambda fraction, message: _say(
                {"progress": round(fraction, 4), "message": message}
            ),
        )
        protocol.writeResult(
            argv[0],
            probabilities,
            {"finalLoss": finalLoss, "device": models.device().type},
        )
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
