"""
Module defining several outputs for the object recognition pipeline
"""

from object_recognition_core.io.source import Source
from image_pipeline.io.source import create_source

########################################################################################################################

class BagReader(Source):

    @classmethod
    def type_name(cls):
        return 'bag_reader'

    @classmethod
    def source(self, *args, **kwargs):
        return create_source(*('image_pipeline', 'BagReader'), **kwargs)
