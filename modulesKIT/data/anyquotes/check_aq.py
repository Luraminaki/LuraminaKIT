"""One-off script: flags anime entries in AQ.txt whose character names collide
after word-order/casing is ignored (e.g. two different-looking names that are
really the same person), so they can be reviewed and merged by hand. Not part
of the anyquotes module itself -- run manually against the raw source data,
not against the shipped `*.csv` files.
"""

import pathlib

AQ_FILE = pathlib.Path('./data/AQ.txt')

lines: list[str] = []
animes: dict[str, dict[str, set[str]]] = {}


with AQ_FILE.open('r', encoding='utf-8') as faq:
    for line in faq.readlines():
        anime, character, quote = tuple(line.replace('\n', '').split("	", maxsplit=3))
        anime = anime.replace('(', '').replace(')', '').title()
        character = character.title()

        if anime not in animes:
            animes[anime] = {'characters': set()}

        animes[anime]['characters'].add(character)
        lines.append(f"{anime}	{character}	{quote}\n")

NEW_AQ_FILE = pathlib.Path('./data/AQ_new.txt')

with NEW_AQ_FILE.open('w', encoding='utf-8') as faq:
    for anime in animes:
        characters = animes[anime]['characters']

        if len(characters) == 1:
            continue

        unique_names: set[tuple[str, ...]] = set()
        for character_name in characters:
            unique_names.add(tuple(set(sorted(character_name.split(' ')))))

        if len(unique_names) == len(characters):
            continue

        faq.writelines(f"{anime} -- {', '.join(list(sorted(characters)))}\n")
