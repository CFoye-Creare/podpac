import pytest

import numpy as np
from traitlets import TraitError

from podpac.core.coordinates import Coordinates, clinspace
from podpac.core.units import UnitsDataArray
from podpac.core.node import Node
from podpac.core.algorithm.utility import Arange
from podpac.core.data.datasource import DataSource
from podpac.core.data.array_source import Array
from podpac.core.data.reprojection import ReprojectedSource


class TestReprojectedSource(object):

    """Test Reprojected Source
    TODO: this needs to be reworked with real examples
    """

    data = np.random.rand(11, 11)
    native_coordinates = Coordinates([clinspace(-25, 25, 11), clinspace(-25, 25, 11)], dims=["lat", "lon"])
    reprojected_coordinates = Coordinates([clinspace(-25, 50, 11), clinspace(-25, 50, 11)], dims=["lat", "lon"])

    def test_init(self):
        """test basic init of class"""

        node = ReprojectedSource(source=Node(), reprojected_coordinates=self.reprojected_coordinates)
        assert isinstance(node, ReprojectedSource)

    def test_native_coordinates(self):
        """test native coordinates"""

        # source has no native_coordinates, just use reprojected_coordinates
        node = ReprojectedSource(source=Node(), reprojected_coordinates=self.reprojected_coordinates)
        assert node.native_coordinates == self.reprojected_coordinates

        # source has native_coordinates
        source = Array(native_coordinates=self.native_coordinates)
        node = ReprojectedSource(source=source, reprojected_coordinates=self.reprojected_coordinates)
        assert node.native_coordinates == self.reprojected_coordinates

    def test_get_data(self):
        """test get data from reprojected source"""
        source = Array(data=self.data, native_coordinates=self.native_coordinates)
        node = ReprojectedSource(source=source, reprojected_coordinates=source.native_coordinates)
        output = node.eval(node.native_coordinates)

    def test_source_interpolation(self):
        """test get data from reprojected source"""

        # no source_interpolation
        source = Array(data=self.data, native_coordinates=self.native_coordinates, interpolation="nearest")
        node = ReprojectedSource(source=source, reprojected_coordinates=self.reprojected_coordinates)
        assert source.interpolation == "nearest"
        assert node.source.interpolation == "nearest"
        assert node.eval_source.interpolation == "nearest"
        assert node.eval_source.native_coordinates == source.native_coordinates
        np.testing.assert_array_equal(node.eval_source.data, source.data)

        # matching source_interpolation
        source = Array(data=self.data, native_coordinates=self.native_coordinates, interpolation="nearest")
        node = ReprojectedSource(
            source=source, reprojected_coordinates=self.reprojected_coordinates, source_interpolation="nearest"
        )
        assert source.interpolation == "nearest"
        assert node.source.interpolation == "nearest"
        assert node.eval_source.interpolation == "nearest"
        assert node.eval_source.native_coordinates == source.native_coordinates
        np.testing.assert_array_equal(node.eval_source.data, source.data)

        # non-matching source_interpolation
        source = Array(data=self.data, native_coordinates=self.native_coordinates, interpolation="nearest")
        node = ReprojectedSource(
            source=source, reprojected_coordinates=self.reprojected_coordinates, source_interpolation="bilinear"
        )
        assert source.interpolation == "nearest"
        assert node.source.interpolation == "nearest"
        assert node.eval_source.interpolation == "bilinear"
        assert node.eval_source.native_coordinates == source.native_coordinates
        np.testing.assert_array_equal(node.eval_source.data, source.data)

        # no source.interpolation to set (trigger logger warning)
        source = Node()
        node = ReprojectedSource(
            source=source, reprojected_coordinates=self.reprojected_coordinates, source_interpolation="bilinear"
        )

    def test_interpolation_warning(self):
        node = ReprojectedSource(source=Arange(), reprojected_coordinates=self.native_coordinates)
        output = node.eval(node.native_coordinates)

    def test_base_ref(self):
        """test base ref"""

        node = ReprojectedSource(source=Node(), reprojected_coordinates=self.reprojected_coordinates)
        assert "_reprojected" in node.base_ref

    def test_deserialize_reprojected_coordinates(self):
        node1 = ReprojectedSource(source=Node(), reprojected_coordinates=self.reprojected_coordinates)
        node2 = ReprojectedSource(source=Node(), reprojected_coordinates=self.reprojected_coordinates.definition)
        node3 = ReprojectedSource(source=Node(), reprojected_coordinates=self.reprojected_coordinates.json)

        assert node1.reprojected_coordinates == self.reprojected_coordinates
        assert node2.reprojected_coordinates == self.reprojected_coordinates
        assert node3.reprojected_coordinates == self.reprojected_coordinates
