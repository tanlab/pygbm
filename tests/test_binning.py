import numpy as np
from numpy.testing import assert_array_equal, assert_allclose
import pytest

from pygbm.binning import BinMapper, find_bins, map_to_bins


DATA = np.random.RandomState(42).normal(
    loc=[0, 10], scale=[1, 0.01], size=(int(1e6), 2)
).astype(np.float32)


def test_find_bins_regular_data():
    data = np.linspace(0, 10, 1000).reshape(-1, 1)
    bin_thresholds = find_bins(data, max_bins=10)
    assert_allclose(bin_thresholds[0], [1, 2, 3, 4, 5, 6, 7, 8, 9])

    bin_thresholds = find_bins(data, max_bins=5)
    assert_allclose(bin_thresholds[0], [2, 4, 6, 8])


def test_find_bins_random_data():
    bin_thresholds = find_bins(DATA, random_state=0)
    assert bin_thresholds.shape == (2, 254)  # 255 (default) - 1
    assert bin_thresholds.dtype == DATA.dtype

    assert_allclose(bin_thresholds[0][[64, 128, 192]],
                    np.array([-0.7, 0.0, 0.7]), atol=1e-1)

    assert_allclose(bin_thresholds[1][[64, 128, 192]],
                    np.array([9.99, 10.00, 10.01]), atol=1e-2)


def test_find_bins_low_n_bins():
    bin_thresholds = find_bins(DATA, max_bins=128, random_state=0)
    assert bin_thresholds.shape == (2, 127)
    assert bin_thresholds.dtype == DATA.dtype


def test_find_bins_invalid_n_bins():
    with pytest.raises(ValueError):
        find_bins(DATA, max_bins=1024)


@pytest.mark.parametrize('n_bins', [16, 128, 256])
def test_map_to_bins(n_bins):
    bins = find_bins(DATA, max_bins=n_bins, random_state=0)
    binned = map_to_bins(DATA, bins)
    assert binned.shape == DATA.shape
    assert binned.dtype == np.uint8
    assert binned.flags.f_contiguous

    min_indices = DATA.argmin(axis=0)
    max_indices = DATA.argmax(axis=0)

    for feature_idx, min_idx in enumerate(min_indices):
        assert binned[min_idx, feature_idx] == 0
    for feature_idx, max_idx in enumerate(max_indices):
        assert binned[max_idx, feature_idx] == n_bins - 1


@pytest.mark.parametrize("n_bins", [5, 10, 42])
def test_bin_mapper_random_data(n_bins):
    n_samples, n_features = DATA.shape

    expected_count_per_bin = n_samples // n_bins
    tol = int(0.05 * expected_count_per_bin)

    mapper = BinMapper(max_bins=n_bins, random_state=42).fit(DATA)
    binned = mapper.transform(DATA)

    assert binned.shape == (n_samples, n_features)
    assert binned.dtype == np.uint8
    assert_array_equal(binned.min(axis=0), np.array([0, 0]))
    assert_array_equal(binned.max(axis=0), np.array([n_bins - 1, n_bins - 1]))
    assert mapper.bin_thresholds_.shape == (n_features, n_bins - 1)

    # Check that the binned data is approximately balanced across bins.
    for feature_idx in range(n_features):
        for bin_idx in range(n_bins):
            count = (binned[:, feature_idx] == bin_idx).sum()
            assert abs(count - expected_count_per_bin) < tol


@pytest.mark.parametrize("n_bins, multiplier", [
    (5, 1),
    (5, 3),
    (255, 42),
])
def test_bin_mapper_identity(n_bins, multiplier):
    data = np.array(list(range(n_bins)) * multiplier).reshape(-1, 1)
    binned = BinMapper(max_bins=n_bins).fit_transform(data)
    assert_array_equal(data, binned)


@pytest.mark.parametrize("n_bins, scale, offset", [
    (3, 2, -1),
    (42, 1, 0),
    (256, 0.3, 42),
])
def test_bin_mapper_identity_small(n_bins, scale, offset):
    data = np.arange(n_bins).reshape(-1, 1) * scale + offset
    binned = BinMapper(max_bins=n_bins).fit_transform(data)
    assert_array_equal(binned, np.arange(n_bins).reshape(-1, 1))


@pytest.mark.parametrize('n_bins_small, n_bins_large', [
    (1, 1),
    (3, 3),
    (4, 4),
    (42, 42),
    (256, 256),
    # (5, 17),  # TODO: implement max_bins == n_unique
    # (42, 256),
])
def test_bin_mapper_idempotence(n_bins_small, n_bins_large):
    assert n_bins_large >= n_bins_small
    data = np.random.RandomState(42).normal(size=300).reshape(-1, 1)
    binned_small = BinMapper(max_bins=n_bins_small).fit_transform(data)
    binned_large = BinMapper(max_bins=n_bins_large).fit_transform(binned_small)
    assert_array_equal(binned_small, binned_large)
