"""Varda's PyTorch worker: trains and applies the CNN and ViT patch classifiers.

It needs only numpy and torch, so it runs either inside Varda (when torch is
importable there) or in the separate PyTorch environment that Varda's
Optional Features dialog installs:

    python -m varda_torch_worker JOBDIR     # run a job (see ``protocol``)
    python -m varda_torch_worker --probe    # print the torch version and device

``patches`` and ``protocol`` need only numpy; ``models`` and ``job`` need torch.
"""
