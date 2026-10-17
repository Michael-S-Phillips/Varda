"""The spectral hourglass pipeline model: steps, staleness and endmembers."""

import numpy as np
import pytest

from synthetic_scene import WAVELENGTHS, endmemberSpectra, syntheticScene
from varda.workspaces.spectral_hourglass.hourglass_model import (
    HourglassModel,
    MapMethod,
    Step,
    StepState,
)


def _noProgress(percent, message):
    pass


def _prepared(**settings) -> HourglassModel:
    image, _ = syntheticScene()
    model = HourglassModel(image)
    for key, value in settings.items():
        setattr(model.settings, key, value)
    model.applyPrepared(model.prepareTask()(_noProgress))
    return model


def _throughPpi() -> HourglassModel:
    model = _prepared()
    model.applyMnf(model.mnfTask()(_noProgress))
    model.setComponents(3)
    model.applyPpi(model.ppiTask(iterations=3000, threshold=0.5, seed=0)(_noProgress))
    return model


def test_new_model_has_nothing_run():
    image, _ = syntheticScene()
    model = HourglassModel(image)
    assert all(model.state(step) is StepState.NOT_RUN for step in Step)
    assert model.endmembers == []


def test_prepare_subsets_bands_by_wavelength_and_marks_nodata():
    model = _prepared(wavelengthRange=(1200.0, 2400.0))
    keep = (WAVELENGTHS >= 1200.0) & (WAVELENGTHS <= 2400.0)
    assert model.state(Step.PREPARE) is StepState.DONE
    assert model.wavelengths is not None
    np.testing.assert_allclose(model.wavelengths, WAVELENGTHS[keep])
    assert model.cube.shape == (40, 36, keep.sum())
    assert not model.valid[0, 0] and model.valid.sum() == 40 * 36 - 1


def test_prepare_can_run_the_iovf_filter():
    model = _prepared(useIovf=True)
    assert model.state(Step.PREPARE) is StepState.DONE
    assert np.isfinite(model.cube[1:, 1:]).all()


def test_mnf_suggests_a_component_count_and_gives_component_images():
    model = _prepared()
    model.applyMnf(model.mnfTask()(_noProgress))
    assert model.state(Step.REDUCE) is StepState.DONE
    assert 1 <= model.components <= model.cube.shape[2]
    image = model.componentImage(0)
    assert image.shape == (40, 36) and np.isnan(image[0, 0])


def test_rerunning_an_earlier_step_marks_later_steps_stale():
    model = _throughPpi()
    assert model.state(Step.PURITY) is StepState.DONE
    model.applyPrepared(model.prepareTask()(_noProgress))
    assert model.state(Step.REDUCE) is StepState.STALE
    assert model.state(Step.PURITY) is StepState.STALE
    model.applyMnf(model.mnfTask()(_noProgress))
    assert model.state(Step.REDUCE) is StepState.DONE
    assert model.state(Step.PURITY) is StepState.STALE


def test_changing_the_component_count_marks_purity_stale():
    model = _throughPpi()
    model.setComponents(2)
    assert model.state(Step.PURITY) is StepState.STALE


def test_ppi_finds_the_pure_patches_as_candidates():
    model = _throughPpi()
    ppi = model.ppiImage()
    assert ppi.shape == (40, 36) and np.isnan(ppi[0, 0])
    model.setCandidateRule(minCount=1, maxCandidates=200)
    candidates = model.candidatePixels()
    assert 0 < candidates.size <= 200
    rows, cols = np.unravel_index(candidates[:40], (40, 36))
    corners = [(2, 2), (2, 30), (34, 2)]
    hits = {
        k
        for k, (r0, c0) in enumerate(corners)
        for r, c in zip(rows, cols)
        if r0 <= r < r0 + 4 and c0 <= c < c0 + 4
    }
    assert hits == {0, 1, 2}
    assert model.ndPoints().shape == (candidates.size, 3)


def test_ppi_can_continue_adding_iterations():
    model = _throughPpi()
    before = np.nansum(model.ppiImage())
    model.applyPpi(
        model.ppiTask(iterations=1000, threshold=0.5, seed=0, resume=True)(_noProgress)
    )
    assert np.nansum(model.ppiImage()) > before
    assert model.ppiIterations == 4000


def test_the_mnf_image_keeps_its_noise_model():
    model = _mnfWithComponents(3)
    info = model.mnfMetadata()["transform"]
    bands = model.cube.shape[2]
    assert np.asarray(info["noiseCovariance"]).shape == (bands, bands)
    assert len(info["noiseSigma"]) == bands
    assert info["noiseEstimate"] == "HORIZONTAL"


def _mnfWithComponents(count: int) -> HourglassModel:
    model = _prepared()
    model.applyMnf(model.mnfTask()(_noProgress))
    model.setComponents(count)
    return model


def test_ppi_records_its_seed_threshold_and_components():
    model = _throughPpi()
    assert model.ppi is not None
    assert (model.ppi.seed, model.ppi.iterations) == (0, 3000)
    assert (model.ppi.threshold, model.ppi.components) == (0.5, 3)


def test_run_more_continues_the_seeded_skewers_so_the_total_determines_the_counts():
    model = _throughPpi()  # 3000 skewers, seed 0
    model.applyPpi(
        model.ppiTask(iterations=1000, threshold=0.5, seed=0, resume=True)(_noProgress)
    )
    once = _mnfWithComponents(3)
    once.applyPpi(once.ppiTask(iterations=4000, threshold=0.5, seed=0)(_noProgress))
    assert model.ppi is not None and once.ppi is not None
    np.testing.assert_array_equal(model.ppi.counts, once.ppi.counts)


def test_run_more_is_refused_once_the_ppi_settings_change():
    model = _throughPpi()
    assert model.canRunMore(0.5, 0)
    assert not model.canRunMore(0.6, 0)
    assert not model.canRunMore(0.5, 1)
    model.setComponents(2)
    assert not model.canRunMore(0.5, 0)
    with pytest.raises(ValueError):
        model.ppiTask(iterations=1000, threshold=0.5, seed=0, resume=True)


def test_saved_ppi_records_the_seed_and_total_iterations():
    model = _throughPpi()
    model.applyPpi(
        model.ppiTask(iterations=1000, threshold=0.5, seed=0, resume=True)(_noProgress)
    )
    assert model.ppi is not None
    counts = model.ppi.counts.copy()
    data = model.ppiToJson()
    assert data is not None
    assert (data["seed"], data["totalIterations"]) == (0, 4000)
    assert (data["threshold"], data["components"]) == (0.5, 3)

    model.resetFrom(Step.PURITY)
    model.ppiFromJson(data)
    assert model.ppi is not None
    np.testing.assert_array_equal(model.ppi.counts, counts)
    assert (model.ppi.seed, model.ppi.iterations) == (0, 4000)
    assert model.canRunMore(0.5, 0)


def test_ppi_saved_before_seeds_were_recorded_loads_but_cannot_run_more():
    model = _throughPpi()
    data = model.ppiToJson()
    assert data is not None
    legacy = {key: data[key] for key in ("validPixels", "rows", "counts", "threshold")}
    legacy["iterations"] = 3000
    model.resetFrom(Step.PURITY)
    model.ppiFromJson(legacy)
    assert model.ppi is not None
    assert model.ppi.seed is None and model.ppi.iterations == 3000
    assert not model.canRunMore(0.5, 0)


def test_endmembers_own_their_pixels_exclusively():
    model = _throughPpi()
    a = model.addEndmember()
    b = model.addEndmember()
    assert a.name == "Endmember 1" and b.name == "Endmember 2"
    assert a.color != b.color
    model.assignPixels(a.id, [5, 6, 7])
    model.assignPixels(b.id, [7, 8])
    assert list(model.endmember(a.id).pixels) == [5, 6]
    assert list(model.endmember(b.id).pixels) == [7, 8]
    model.assignPixels(b.id, [8], add=False)
    assert list(model.endmember(b.id).pixels) == [7]
    assert model.state(Step.ENDMEMBERS) is StepState.DONE


def test_endmember_spectrum_is_the_mean_of_its_pixels():
    model = _prepared()
    em = model.addEndmember()
    clayPatch = [r * 36 + c for r in range(2, 6) for c in range(30, 34)]
    model.assignPixels(em.id, clayPatch)
    np.testing.assert_allclose(
        model.endmemberSpectrum(em.id), endmemberSpectra()[1], atol=0.005
    )


def test_rename_merge_and_remove_endmembers():
    model = _throughPpi()
    a, b = model.addEndmember(), model.addEndmember()
    model.assignPixels(a.id, [1, 2])
    model.assignPixels(b.id, [3])
    model.renameEndmember(a.id, "Kaolinite")
    merged = model.mergeEndmembers([a.id, b.id])
    assert merged.name == "Kaolinite" and sorted(merged.pixels) == [1, 2, 3]
    assert [e.id for e in model.endmembers] == [merged.id]
    model.removeEndmember(merged.id)
    assert model.endmembers == []
    assert model.state(Step.ENDMEMBERS) is StepState.NOT_RUN


def test_suggested_endmembers_are_the_pure_patches():
    model = _throughPpi()
    model.setCandidateRule(minCount=1, maxCandidates=300)
    created = model.suggestEndmembers(3)
    assert len(created) == 3 and len(model.endmembers) == 3
    truth = endmemberSpectra()
    for endmember in created:
        spectrum = model.endmemberSpectrum(endmember.id)
        assert np.min(np.abs(truth - spectrum).max(axis=1)) < 0.03


def _withTrueEndmembers() -> HourglassModel:
    model = _throughPpi()
    for name, (r0, c0) in zip(["flat", "clay", "mafic"], [(2, 2), (2, 30), (34, 2)]):
        em = model.addEndmember(name)
        model.assignPixels(
            em.id, [r * 36 + c for r in range(r0, r0 + 4) for c in range(c0, c0 + 4)]
        )
    return model


def test_sam_map_classifies_the_pure_patches():
    model = _withTrueEndmembers()
    result = model.applyMap(model.mapTask(MapMethod.SAM, maxAngle=0.1)(_noProgress))
    assert result.bandNames == ["Class", "Angle(flat)", "Angle(clay)", "Angle(mafic)"]
    assert result.extraMetadata["classes"] == ["flat", "clay", "mafic"]
    assert len(result.extraMetadata["classColors"]) == 3
    classes = result.getData()[:, :, 0]
    assert classes[3, 3] == 0 and classes[3, 31] == 1 and classes[35, 3] == 2
    assert np.isnan(classes[0, 0])
    assert model.state(Step.MAP) is StepState.DONE


def test_unmixing_map_recovers_abundances():
    image, truth = syntheticScene()
    model = _withTrueEndmembers()
    result = model.mapTask(MapMethod.UNMIX)(_noProgress)
    assert result.bandNames == ["flat", "clay", "mafic", "RMS Error"]
    abundances = result.getData()[1:, 1:, :3]
    assert np.abs(abundances - truth[1:, 1:]).mean() < 0.03


def test_mtmf_map_scores_the_clay_patch():
    model = _withTrueEndmembers()
    result = model.mapTask(MapMethod.MTMF)(_noProgress)
    assert result.bandNames[:2] == ["MF(flat)", "MF(clay)"]
    assert "Infeasibility(clay)" in result.bandNames
    mf = result.getData()[:, :, result.bandNames.index("MF(clay)")]
    assert mf[3, 31] == pytest.approx(1.0, abs=0.2)


def test_mapping_needs_two_endmembers_with_pixels():
    model = _throughPpi()
    model.addEndmember()
    with pytest.raises(ValueError, match="at least two endmembers"):
        model.mapTask(MapMethod.SAM)(_noProgress)


def test_endmembers_round_trip_through_json():
    model = _withTrueEndmembers()
    model.renameEndmember(model.endmembers[1].id, "Kaolinite")
    model.setIdentification(model.endmembers[1].id, "Kaolinite KGa-1 (0.92)")
    data = model.endmembersToJson()

    fresh = _throughPpi()
    fresh.endmembersFromJson(data)
    assert [e.name for e in fresh.endmembers] == ["flat", "Kaolinite", "mafic"]
    assert [list(e.pixels) for e in fresh.endmembers] == [
        list(e.pixels) for e in model.endmembers
    ]
    assert [e.color for e in fresh.endmembers] == [e.color for e in model.endmembers]
    assert fresh.endmembers[1].identification == "Kaolinite KGa-1 (0.92)"


def test_endmember_edits_can_be_undone():
    model = _throughPpi()
    assert not model.canUndo()
    a = model.addEndmember()
    model.assignPixels(a.id, [1, 2, 3])
    model.assignPixels(a.id, [4, 5])
    model.renameEndmember(a.id, "Kaolinite")

    assert model.undo()
    assert model.endmember(a.id).name == "Endmember 1"
    assert model.undo()
    assert list(model.endmember(a.id).pixels) == [1, 2, 3]
    assert model.undo() and model.endmember(a.id).pixels.size == 0
    assert model.undo() and model.endmembers == []
    assert not model.canUndo() and not model.undo()


def test_undo_restores_a_merge_and_notifies():
    model = _throughPpi()
    a, b = model.addEndmember(), model.addEndmember()
    model.assignPixels(a.id, [1])
    model.assignPixels(b.id, [2])
    seen = []
    model.sigEndmembersChanged.connect(lambda: seen.append(True))
    model.mergeEndmembers([a.id, b.id])
    model.undo()
    assert [list(e.pixels) for e in model.endmembers] == [[1], [2]]
    assert len(seen) == 2


def test_starting_over_from_a_step_clears_it_and_everything_after():
    model = _withTrueEndmembers()
    model.applyMap(model.mapTask(MapMethod.SAM)(_noProgress))
    model.resetFrom(Step.PURITY)
    assert model.ppi is None and model.state(Step.PURITY) is StepState.NOT_RUN
    assert model.state(Step.MAP) is StepState.NOT_RUN
    assert model.mnf is not None and model.state(Step.REDUCE) is StepState.DONE
    assert len(model.endmembers) == 3  # pixel classes survive an earlier restart

    model.resetFrom(Step.PREPARE)
    assert model.prepared is None and model.mnf is None
    assert all(
        model.state(s) is StepState.NOT_RUN
        for s in (Step.PREPARE, Step.REDUCE, Step.PURITY)
    )


def test_starting_over_from_endmembers_clears_them_undoably():
    model = _withTrueEndmembers()
    model.setIdentification(model.endmembers[0].id, "Flat (0.9)")
    model.resetFrom(Step.ENDMEMBERS)
    assert model.endmembers == [] and model.state(Step.ENDMEMBERS) is StepState.NOT_RUN
    model.undo()
    assert len(model.endmembers) == 3


def test_starting_over_from_identify_clears_identifications_only():
    model = _withTrueEndmembers()
    model.setIdentification(model.endmembers[0].id, "Flat (0.9)")
    model.markIdentified()
    model.resetFrom(Step.IDENTIFY)
    assert model.endmembers[0].identification == "" and len(model.endmembers) == 3
    assert model.state(Step.IDENTIFY) is StepState.NOT_RUN


def test_ppi_counts_round_trip_compactly():
    model = _throughPpi()
    saved = model.ppiToJson()
    assert saved is not None and model.ppi is not None
    assert len(saved["rows"]) == int((model.ppi.counts > 0).sum())
    fresh = _prepared()
    fresh.applyMnf(fresh.mnfTask()(_noProgress))
    fresh.ppiFromJson(saved)
    assert fresh.ppi is not None
    np.testing.assert_array_equal(fresh.ppi.counts, model.ppi.counts)
    assert fresh.ppiIterations == model.ppiIterations
    assert fresh.state(Step.PURITY) is StepState.DONE


def test_prepare_records_nanometre_centres_whatever_the_unit():
    image, _ = syntheticScene(units="µm")
    model = HourglassModel(image)
    model.applyPrepared(model.prepareTask()(lambda p, m: None))
    np.testing.assert_allclose(model.wavelengths, WAVELENGTHS / 1000)  # own unit
    np.testing.assert_allclose(model.wavelengthsNm, WAVELENGTHS)


def test_prepare_leaves_out_bands_marked_bad_in_the_header():
    bbl = np.ones(WAVELENGTHS.size, dtype=int)
    bbl[[5, 6, 40]] = 0
    image, _ = syntheticScene(
        extraMetadata={"bbl": "{" + ",".join(map(str, bbl)) + "}"}
    )
    model = HourglassModel(image)
    model.applyPrepared(model.prepareTask()(lambda p, m: None))
    assert model.prepared is not None
    assert 5 not in model.prepared.bandIndices and 40 not in model.prepared.bandIndices
    assert model.prepared.cube.shape[2] == WAVELENGTHS.size - 3
