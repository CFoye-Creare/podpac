"""
Test podpac.core.data.datasource module
"""

import pytest

from traitlets import TraitError
import numpy as np
from xarray.core.coordinates import DataArrayCoordinates
import xarray as xr

from podpac.core.units import UnitsDataArray
from podpac.core.node import COMMON_NODE_DOC
from podpac.core.style import Style
from podpac.core.coordinates import Coordinates, clinspace, crange
from podpac.core.data.datasource import DataSource, COMMON_DATA_DOC, DATA_DOC

class MockArrayDataSource(DataSource):
    def get_data(self, coordinates, coordinates_index):
        return self.create_output_array(coordinates, data=self.source[coordinates_index])

class MockDataSource(DataSource):
    data = np.ones((101, 101))
    data[0, 0] = 10
    data[0, 1] = 1
    data[1, 0] = 5
    data[1, 1] = None

    def get_native_coordinates(self):
        return Coordinates([clinspace(-25, 25, 101), clinspace(-25, 25, 101)], dims=['lat', 'lon'])

    def get_data(self, coordinates, coordinates_index):
        return self.create_output_array(coordinates, data=self.data[coordinates_index])

class MockNonuniformDataSource(DataSource):
    """ Mock Data Source for testing that is non-uniform """

    # mock 3 x 3 grid of random values
    source = np.random.rand(3, 3)
    native_coordinates = Coordinates([[-10, -2, -1], [4, 32, 1]], dims=['lat', 'lon'])

    def get_native_coordinates(self):
        """ """
        return self.native_coordinates

    def get_data(self, coordinates, coordinates_index):
        """ """
        s = coordinates_index
        d = self.create_output_array(coordinates, data=self.source[s])
        return d

class TestDataDocs(object):
    def test_common_data_doc(self):
        # all DATA_DOC keys should be in the COMMON_DATA_DOC
        for key in DATA_DOC:
            assert key in COMMON_DATA_DOC
            assert COMMON_DATA_DOC[key] == DATA_DOC[key]

        # DATA_DOC should overwrite COMMON_NODE_DOC keys
        for key in COMMON_NODE_DOC:
            assert key in COMMON_DATA_DOC

            if key in DATA_DOC:
                assert COMMON_DATA_DOC[key] != COMMON_NODE_DOC[key]
            else:
                assert COMMON_DATA_DOC[key] == COMMON_NODE_DOC[key]

class TestDataSource(object):
    def test_init(self):
        node = DataSource()

    def test_nomethods_must_be_implemented(self):
        node = DataSource()
        
        with pytest.raises(NotImplementedError):
            node.get_native_coordinates()

        with pytest.raises(NotImplementedError):
            node.get_data(None, None)

    def test_set_native_coordinates(self):
        nc = Coordinates([clinspace(0, 50, 101), clinspace(0, 50, 101)], dims=['lat', 'lon'])
        node = DataSource(source='test', native_coordinates=nc)
        assert node.native_coordinates is not None
        
        with pytest.raises(TraitError):
            DataSource(source='test', native_coordinates='not a coordinate')
        
        with pytest.raises(NotImplementedError):
            DataSource(source='test').native_coordinates

    def test_get_native_coordinates(self):
        # get_native_coordinates should set the native_coordinates by default
        node = MockDataSource()
        assert node.native_coordinates is not None
        np.testing.assert_equal(node.native_coordinates['lat'].coordinates, np.linspace(-25, 25, 101))
        np.testing.assert_equal(node.native_coordinates['lon'].coordinates, np.linspace(-25, 25, 101))

        # but don't call get_native_coordinates if the native_coordinates are set explicitly
        nc = Coordinates([clinspace(0, 50, 101), clinspace(0, 50, 101)], dims=['lat', 'lon'])
        node = MockDataSource(native_coordinates=nc)
        assert node.native_coordinates is not None
        np.testing.assert_equal(node.native_coordinates['lat'].coordinates, nc['lat'].coordinates)
        np.testing.assert_equal(node.native_coordinates['lat'].coordinates, nc['lat'].coordinates)

    def test_invalid_interpolation(self):
        with pytest.raises(TraitError):
            MockDataSource(interpolation='myowninterp')

    def test_invalid_nan_vals(self):
        with pytest.raises(TraitError):
            MockDataSource(nan_vals={})

        with pytest.raises(TraitError):
            MockDataSource(nan_vals=10)

    def test_base_definition(self):
        """Test definition property method"""

        node = DataSource(source='test')
        d = node.base_definition

        assert d
        assert 'node' in d
        assert d['source'] == node.source

        # TODO: add interpolation definition testing

    def test_evaluate_at_native_coordinates(self):
        """evaluate node at native coordinates"""

        node = MockDataSource()
        output = node.eval(node.native_coordinates)

        assert isinstance(output, UnitsDataArray)
        assert output.shape == (101, 101)
        assert output[0, 0] == 10
        assert output.lat.shape == (101,)
        assert output.lon.shape == (101,)

        # assert coordinates
        assert isinstance(output.coords, DataArrayCoordinates)
        assert output.coords.dims == ('lat', 'lon')

        # assert attributes
        assert isinstance(output.attrs['layer_style'], Style)

    def test_evaluate_with_output(self):
        node = MockDataSource()

        # initialize a large output array
        fullcoords = Coordinates([crange(20, 30, 1), crange(20, 30, 1)], dims=['lat', 'lon'])
        output = UnitsDataArray(np.ones(fullcoords.shape), coords=fullcoords.coords, dims=fullcoords.dims)
        
        # evaluate a subset of the full coordinates
        coords = Coordinates([fullcoords['lat'][3:8], fullcoords['lon'][3:8]])
        
        # after evaluation, the output should be
        # - the same where it was not evaluated
        # - NaN where it was evaluated but doesn't intersect with the data source
        # - 0 where it was evaluated and does intersect with the data source (because this datasource is all 0)
        expected = output.copy()
        expected[3:8, 3:8] = np.nan
        expected[3:6, 3:6] = 0

        # evaluate the subset coords, passing in the cooresponding slice of the initialized output array
        node.eval(coords, output=output[3:8, 3:8])
        np.testing.assert_equal(output.data, expected.data)

    def test_evaluate_with_output_no_intersect(self):
        # there is a shortcut if there is no intersect, so we test that here
        node = MockDataSource()
        coords = Coordinates([clinspace(30, 40, 10), clinspace(30, 40, 10)], dims=['lat', 'lon'])
        output = UnitsDataArray(np.ones(coords.shape), coords=coords.coords, dims=coords.dims)
        node.eval(coords, output=output)
        np.testing.assert_equal(output.data, np.full(output.shape, np.nan))

    def test_evaluate_with_output_transpose(self):
        # initialize coords with dims=[lon, lat]
        lon = clinspace(10, 15, 6)
        lat = clinspace(10, 20, 11)
        coords = Coordinates([lon, lat], dims=['lon', 'lat'])
        
        # evaluate with dims=[lat, lon], passing in the output
        node = MockDataSource()
        output = node.create_output_array(coords.transpose('lat', 'lon'))
        node.eval(coords, output=output)
        
        # dims should stay in the order of the output, rather than the order of the requested coordinates
        assert output.dims == ('lon', 'lat')

    def test_evaluate_extra_dims(self):
        # drop extra dimension
        node = MockArrayDataSource(
            source=np.empty((3, 2)),
            native_coordinates=Coordinates([[0, 1, 2], [10, 11]], dims=['lat', 'lon']),
            interpolation='nearest_preview')

        output = node.eval(Coordinates([1, 11, '2018-01-01'], dims=['lat', 'lon', 'time']))
        assert output.dims == ('lat', 'lon') # time dropped

        # drop extra stacked dimension if none of its dimensions are needed 
        node = MockArrayDataSource(
            source=np.empty((2)),
            native_coordinates=Coordinates([['2018-01-01', '2018-01-02']], dims=['time']),
            interpolation='nearest_preview')
        
        output = node.eval(Coordinates([[1, 11], '2018-01-01'], dims=['lat_lon', 'time']))
        assert output.dims == ('time',) # lat_lon dropped

        # don't drop extra stacked dimension if any of its dimensions are needed
        # TODO interpolation is not yet implemented
        #node = MockArrayDataSource(
            #source=np.empty(3),
            #native_coordinates=Coordinates([[0, 1, 2]], dims=['lat']))
        #output = node.eval(Coordinates([[1, 11]], dims=['lat_lon']))
        #assert output.dims == ('lat_lon') # lon portion not dropped

    def test_evaluate_missing_dims(self):
        # missing unstacked dimension
        node = MockArrayDataSource(
            source=np.empty((3, 2)),
            native_coordinates=Coordinates([[0, 1, 2], [10, 11]], dims=['lat', 'lon']))

        with pytest.raises(ValueError, match="Cannot evaluate these coordinates.*"):
            node.eval(Coordinates([1], dims=['lat']))
        with pytest.raises(ValueError, match="Cannot evaluate these coordinates.*"):
            node.eval(Coordinates([11], dims=['lon']))
        with pytest.raises(ValueError, match="Cannot evaluate these coordinates.*"):
            node.eval(Coordinates(['2018-01-01'], dims=['time']))

        # missing any part of stacked dimension
        node = MockArrayDataSource(
            source=np.empty(3),
            native_coordinates=Coordinates([[[0, 1, 2], [10, 11, 12]]], dims=['lat_lon']))
        
        with pytest.raises(ValueError, match="Cannot evaluate these coordinates.*"):
            node.eval(Coordinates([1], dims=['time']))

        with pytest.raises(ValueError, match="Cannot evaluate these coordinates.*"):
            node.eval(Coordinates([1], dims=['lat']))

    def test_evaluate_no_overlap(self):
        """evaluate node with coordinates that do not overlap"""

        node = MockDataSource()
        coords = Coordinates([clinspace(-55, -45, 20), clinspace(-55, -45, 20)], dims=['lat', 'lon'])
        output = node.eval(coords)

        assert np.all(np.isnan(output))
    
    def test_nan_vals(self):
        """ evaluate note with nan_vals """

        node = MockDataSource(nan_vals=[10, None])
        output = node.eval(node.native_coordinates)

        assert output.values[np.isnan(output)].shape == (2,)

    def test_get_data_np_array(self):
        class MockDataSourceReturnsArray(MockDataSource):
            def get_data(self, coordinates, coordinates_index):
                return self.data[coordinates_index]

        node = MockDataSourceReturnsArray()
        output = node.eval(node.native_coordinates)

        assert isinstance(output, UnitsDataArray)
        assert node.native_coordinates['lat'].coordinates[4] == output.coords['lat'].values[4]

    def test_get_data_DataArray(self):
        class MockDataSourceReturnsDataArray(MockDataSource):
            def get_data(self, coordinates, coordinates_index):
                return xr.DataArray(self.data[coordinates_index])

        node = MockDataSourceReturnsDataArray()
        output = node.eval(node.native_coordinates)

        assert isinstance(output, UnitsDataArray)
        assert node.native_coordinates['lat'].coordinates[4] == output.coords['lat'].values[4]





class TestInterpolateData(object):
    """test default generic interpolation defaults"""

    def test_one_data_point(self):
        """ test when there is only one data point """
        # TODO: as this is currently written, this would never make it to the interpolater
        pass

    def test_interpolate_time(self):
        """ for now time uses nearest neighbor """

        source = np.random.rand(5)
        coords_src = Coordinates([clinspace(0, 10, 5,)], dims=['time'])
        coords_dst = Coordinates([clinspace(1, 11, 5,)], dims=['time'])

        node = MockArrayDataSource(source=source, native_coordinates=coords_src)
        output = node.eval(coords_dst)

        assert isinstance(output, UnitsDataArray)
        assert np.all(output.time.values == coords_dst.coords['time'])

    def test_interpolate_lat_time(self):
        """interpolate with n dims and time"""
        pass

    def test_interpolate_alt(self):
        """ for now alt uses nearest neighbor """

        source = np.random.rand(5)
        coords_src = Coordinates([clinspace(0, 10, 5)], dims=['alt'])
        coords_dst = Coordinates([clinspace(1, 11, 5)], dims=['alt'])

        node = MockArrayDataSource(source=source, native_coordinates=coords_src)
        output = node.eval(coords_dst)

        assert isinstance(output, UnitsDataArray)
        assert np.all(output.alt.values == coords_dst.coords['alt'])

