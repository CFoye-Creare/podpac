"""
Datasources from files
"""

from __future__ import division, unicode_literals, print_function, absolute_import

import urllib
from io import BytesIO

import traitlets as tl
import xarray as xr

from lazy_import import lazy_module, lazy_class

boto3 = lazy_module("boto3")
s3fs = lazy_module("s3fs")
requests = lazy_module("requests")

from podpac.core.utils import common_doc
from podpac.core.data.datasource import COMMON_DATA_DOC, DataSource
from podpac.core.coordinates import Coordinates

# TODO common doc


class BaseFileSource(DataSource):
    """
    Base class for data sources loaded from file.

    Attributes
    ----------
    source : str
        Path to the data source.
    native_coordinates : Coordinates
        {native_coordinates}
    dataset : Any
        dataset object
    """

    source = tl.Unicode().tag(attr=True)

    @tl.default("source")
    def _default_source(self):
        raise ValueError("%s 'source' required" % self.__class__.__name__)

    # -------------------------------------------------------------------------
    # public api properties and methods
    # -------------------------------------------------------------------------

    @property
    def dataset(self):
        raise NotImplementedError()

    def close_dataset(self):
        """ Close opened resources. Subclasses should implement if appropriate. """
        pass


class LoadFileMixin(tl.HasTraits):
    """
    Mixin to load and cache files using various transport protocols.

    Attributes
    ----------
    cache_dataset : bool
        Whether to cache the dataset after loading.
    """

    cache_dataset = tl.Bool(True)

    @property
    def dataset(self):
        if hasattr(self, "_dataset"):
            return self._dataset

        if self.has_cache(key="dataset"):
            data = self.get_cache(key="dataset")
            with BytesIO(data) as f:
                self._dataset = self._open(BytesIO(data), cache=False)
        elif self.source.startswith("s3://"):
            s3 = s3fs.S3FileSystem(anon=True)  # TODO
            with s3.open(self.source, "rb") as f:
                self._dataset = self._open(f)
        elif self.source.startswith("http://") or self.source.startswith("https://"):
            response = requests.get(self.source)
            with BytesIO(response.content) as f:
                self._dataset = self._open(f)
        elif self.source.startswith("ftp://"):
            addinfourl = urllib.request.urlopen(self.source)
            with BytesIO(addinfourl.read()) as f:
                self._dataset = self._open(f)
        elif self.source.startswith("file://"):
            with urllib.request.urlopen(self.source) as f:
                self._dataset = self._open(f)
        else:
            with open(self.source, "rb") as f:
                self._dataset = self._open(f)

        return self._dataset

    def _open(self, f, cache=True):
        if self.cache_dataset and cache:
            self.put_cache(f.read(), key="dataset")
            f.seek(0)
        return self.open_dataset(f)

    def open_dataset(self, f):
        """ TODO """
        raise NotImplementedError()


@common_doc(COMMON_DATA_DOC)
class FileKeysMixin(tl.HasTraits):
    """
    Mixin to specify data and coordinates dimensions keys.

    Attributes
    ----------
    lat_key : str
        latitude key, default 'lat'
    lon_key : str
        longitude key, default 'lon'
    time_key : str
        time key, default 'time'
    alt_key : str
        altitude key, default 'alt'
    data_key : str
        data key
    output_keys : list
        list of data keys, for multiple-output nodes
    crs : str
        Coordinate reference system of the coordinates.
    cf_time : bool
        decode CF datetimes
    cf_units : str
        units, when decoding CF datetimes
    cf_calendar : str
        calendar, when decoding CF datetimes
    """

    # TODO merge data_key and output_keys
    data_key = tl.Unicode(allow_none=True).tag(attr=True)
    output_keys = tl.List(value=tl.Unicode(), allow_none=True).tag(attr=True)
    lat_key = tl.Unicode(default_value="lat").tag(attr=True)
    lon_key = tl.Unicode(default_value="lon").tag(attr=True)
    time_key = tl.Unicode(default_value="time").tag(attr=True)
    alt_key = tl.Unicode(default_value="alt").tag(attr=True)
    crs = tl.Unicode(allow_none=True, default_value=None).tag(attr=True)
    cf_time = tl.Bool(default_value=False).tag(attr=True)
    cf_units = tl.Unicode(allow_none=True, default_value=None).tag(attr=True)
    cf_calendar = tl.Unicode(allow_none=True, default_value=None).tag(attr=True)

    @tl.default("data_key")
    def _default_data_key(self):
        if self.trait_is_defined("output_keys") and self.output_keys is not None:
            return None
        elif len(self.available_data_keys) == 1:
            return self.available_data_keys[0]
        else:
            return None

    output_keys.default_value = None

    @tl.default("output_keys")
    def _default_output_keys(self):
        if self.trait_is_defined("data_key") and self.data_key is not None:
            return None
        elif len(self.available_data_keys) == 1:
            return None
        else:
            return self.available_data_keys

    @tl.validate("data_key", "output_keys")
    def _validate_data_data_key_output_keys(self, d):
        if (d["trait"].name == "data_key" and d["value"] is not None and self.output_keys is not None) or (
            d["trait"].name == "output_keys" and d["value"] is not None and self.data_key is not None
        ):
            raise TypeError("%s cannot have both data_key and 'output_keys' defined" % (self.__class__.__name__))
        return d["value"]

    @tl.default("outputs")
    def _default_outputs(self):
        return self.output_keys

    @tl.validate("outputs")
    def _validate_outputs(self, d):
        if self.data_key is not None:
            raise TypeError("outputs must be None for single-output nodes")

        if len(d["value"]) != len(self.output_keys):
            raise ValueError(
                "outputs and output_keys size mismatch (%d != %d)" % (len(d["value"]), len(self.output_keys))
            )

        return d["value"]

    # -------------------------------------------------------------------------
    # public api properties and methods
    # -------------------------------------------------------------------------

    @property
    def keys(self):
        raise NotImplementedError

    @property
    def dims(self):
        raise NotImplementedError

    @property
    def available_data_keys(self):
        """available data keys"""
        if not hasattr(self, "_available_data_keys"):
            dim_keys = [self.lat_key, self.lon_key, self.alt_key, self.time_key]
            keys = [key for key in self.keys if key not in dim_keys]
            if len(keys) == 0:
                raise ValueError("No data keys found in '%s'" % self.source)
            self._available_data_keys = keys
        return self._available_data_keys

    def _lookup_key(self, dim):
        lookup = {"lat": self.lat_key, "lon": self.lon_key, "alt": self.alt_key, "time": self.time_key}
        return lookup[dim]

    @common_doc(COMMON_DATA_DOC)
    @property
    def native_coordinates(self):
        """{native_coordinates}
        """

        cs = [self.dataset[self._lookup_key(dim)] for dim in self.dims]
        if self.cf_time and "time" in self.dims:
            time_key = self._lookup_key("time")
            cs[time_key] = xr.coding.times.decode_cf_datetime(cs[time_key], self.cf_units, self.cf_calendar)
        return Coordinates(cs, dims=self.dims, crs=self.crs)
