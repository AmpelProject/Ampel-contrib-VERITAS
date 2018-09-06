
from ampel.pipeline.t3.sergeant import marshal_functions

import pytest

@pytest.fixture
def sergeant():
	return marshal_functions.Sergeant("AMPEL Test", marshalusr="AMPELBOT",marshalpwd="spreepiraten")

def test_instantiate(sergeant):
	pass

def test_get_sources(sergeant):
	assert len(sergeant.get_sourcelist()) > 0
