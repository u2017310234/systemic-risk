"""Expected data availability outcomes, distinct from software failures."""
class DataUnavailable(RuntimeError):
    pass


class PublicationRejected(DataUnavailable):
    pass
