from __future__ import annotations

from game_of_life.engine import Simulation
from game_of_life.models import Action, ActionType, EntityKind, Position, Profession


def test_study_increases_knowledge_and_self_awareness(empty_config) -> None:
    simulation = Simulation(empty_config)
    person = simulation.spawn_human()
    before_awareness = person.self_awareness

    simulation._study(person, "healing")

    assert person.knowledge["healing"] > 0
    assert person.skills["healing"] > 0
    assert person.self_awareness > before_awareness
    assert any(event.event_type == "study" for event in simulation.events)


def test_self_care_changes_visible_identity(empty_config) -> None:
    simulation = Simulation(empty_config)
    person = simulation.spawn_human()
    person.aesthetic_need = 100
    previous = (person.appearance_style, person.appearance_hue, person.accessory)

    simulation._self_care(person)

    assert (person.appearance_style, person.appearance_hue, person.accessory) != previous
    assert person.aesthetic_need == 0
    assert any(event.event_type == "appearance_changed" for event in simulation.events)


def test_conversation_transmits_values_and_personality(empty_config) -> None:
    simulation = Simulation(empty_config)
    speaker = simulation.spawn_human(position=Position(100, 100))
    listener = simulation.spawn_human(position=Position(104, 100))
    speaker.values = {"knowledge": 100}
    speaker.temperament.curiosity = 1
    listener.values = {"knowledge": 10}
    listener.temperament.curiosity = 0.1
    previous_curiosity = listener.temperament.curiosity

    simulation._talk(speaker, listener)

    assert listener.values["knowledge"] > 10
    assert listener.temperament.curiosity > previous_curiosity
    event = next(event for event in simulation.events if event.event_type == "talk")
    assert event.payload["topic"] == "knowledge"
    assert event.payload["influenced_trait"] == "curiosity"


def test_good_and_bad_experiences_change_temperament(empty_config) -> None:
    simulation = Simulation(empty_config)
    person = simulation.spawn_human()
    person.temperament.resilience = 0.2
    previous_aggression = person.temperament.aggression

    simulation._adapt_temperament(person, valence=-1, intensity=1, source="trauma")

    assert person.stress > 0
    assert person.temperament.aggression > previous_aggression
    stressed = person.stress
    previous_empathy = person.temperament.empathy

    simulation._adapt_temperament(person, valence=1, intensity=1, source="kindness")

    assert person.stress < stressed
    assert person.temperament.empathy > previous_empathy


def test_vocation_is_chosen_from_identity_and_social_balance(empty_config) -> None:
    empty_config.vocation_review_interval_ticks = 1
    simulation = Simulation(empty_config)
    for profession in (
        Profession.GATHERER,
        Profession.FARMER,
        Profession.BUILDER,
        Profession.HEALER,
    ):
        worker = simulation.spawn_human()
        worker.profession = profession
        worker.last_vocation_tick = 0
    artist = simulation.spawn_human()
    artist.profession = Profession.UNASSIGNED
    artist.temperament.creativity = 1
    artist.values["beauty"] = 100
    artist.temperament.curiosity = 0
    artist.temperament.empathy = 0
    artist.temperament.sociability = 0
    artist.temperament.discipline = 0
    simulation.state.tick = 1

    simulation._update_vocations()

    assert artist.profession == Profession.ARTIST
    assert artist.goal == "bring beauty and meaning into everyday life"
    assert any(
        event.event_type == "vocation_changed" and event.actor_id == artist.id
        for event in simulation.events
    )


def test_artist_beautifies_a_building(empty_config) -> None:
    simulation = Simulation(empty_config)
    artist = simulation.spawn_human(position=Position(100, 100))
    artist.profession = Profession.ARTIST
    artist.inventory = {"wood": 10, "stone": 3}
    artist.action = Action(ActionType.BUILD, resource="house")
    simulation._resolve(artist)
    building = next(
        entity
        for entity in simulation.state.entities.values()
        if entity.kind == EntityKind.BUILDING
    )
    before = building.beauty
    artist.action_cooldown = 0

    simulation._beautify(artist, building)

    assert building.beauty > before
    assert any(event.event_type == "beautify" for event in simulation.events)
