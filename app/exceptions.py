class GrabzdiaError(Exception):
    """Base class for errors safe to present to the user."""


class InvalidUrlError(GrabzdiaError): pass
class UnsupportedUrlError(GrabzdiaError): pass
class BinaryNotFoundError(GrabzdiaError): pass
class BinaryExecutionError(GrabzdiaError): pass
class MetadataExtractionError(GrabzdiaError): pass
class DownloadError(GrabzdiaError): pass
class InvalidDestinationError(GrabzdiaError): pass
class InsufficientDiskSpaceError(GrabzdiaError): pass
class SettingsError(GrabzdiaError): pass
