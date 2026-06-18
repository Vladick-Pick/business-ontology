#!/usr/bin/env python3
"""links_validate.py - проверка целостности связей онтологии (без зависимостей).

Что проверяет:
  - у каждой карточки есть `id` и `статус`;
  - `id` уникален и непрозрачен (узловой id не содержит `--`);
  - каждый target в блоке `связи` резолвится в существующий `id` (нет висячих ссылок);
  - тип каждой связи входит в закрытый список (см. ai-ready.md / registry-spec.md).

Использование:
  python3 scripts/links_validate.py [корень-онтологии]   # по умолчанию: текущая папка
Код выхода: 0 - чисто, 1 - есть ошибки.

Это поддержка ручной дисциплины, а не замена ей: запускай перед фиксацией правок.
"""
import os
import re
import sys

ALLOWED_LINKS = {
    "производит", "потребляет", "поставляет-в", "часть-чего", "владеет",
    "измеряется", "источник-истины", "в-состоянии", "регулируется",
}

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
ID_RE = re.compile(r"^id:\s*(.+?)\s*$", re.MULTILINE)
STATUS_RE = re.compile(r"^(?:статус|status):\s*(.+?)\s*$", re.MULTILINE)
LINKS_BLOCK = re.compile(r"^связи:\s*\n((?:[ \t]+.*\n?)*)", re.MULTILINE)
LINK_LINE = re.compile(r"^[ \t]+([\wа-яёА-ЯЁ\-]+):\s*\[([^\]]*)\]\s*$")
ID_TOKEN = re.compile(r"[\wа-яёА-ЯЁ\-]+")


def parse_card(text):
    m = FRONTMATTER.search(text)
    if not m:
        return None
    fm = m.group(1)
    idm = ID_RE.search(fm)
    cid = idm.group(1).strip() if idm else None
    has_status = bool(STATUS_RE.search(fm))
    links = []
    lb = LINKS_BLOCK.search(fm)
    if lb:
        for line in lb.group(1).splitlines():
            lm = LINK_LINE.match(line)
            if not lm:
                continue
            rel = lm.group(1)
            targets = [t for t in ID_TOKEN.findall(lm.group(2))]
            # отбрасываем плейсхолдеры шаблонов вида <id>
            targets = [t for t in targets if not t.startswith("<")]
            links.append((rel, targets))
    # Не карточка онтологии: фронтматтер есть, но нет ни id, ни связей
    # (например SKILL.md с name/description). Пропускаем.
    if cid is None and not links:
        return None
    return {"id": cid, "has_status": has_status, "links": links}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    cards = {}
    errors = []
    skip_dirs = {".git", "node_modules", "registry", "scripts"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except Exception as exc:
                errors.append(f"{path}: не прочитан ({exc})")
                continue
            card = parse_card(text)
            if card is None:
                continue  # не карточка (нет фронтматтера)
            rel = os.path.relpath(path, root)
            if not card["id"]:
                errors.append(f"{rel}: нет поля id")
                continue
            cid = card["id"]
            if cid.startswith("<"):
                continue  # шаблон, не настоящая карточка
            if not card["has_status"]:
                errors.append(f"{rel}: нет поля статус")
            if "--" in cid:
                errors.append(f"{rel}: узловой id '{cid}' содержит '--' (похоже на производный; нужен непрозрачный id)")
            if cid in cards:
                errors.append(f"{rel}: дубликат id '{cid}' (также в {cards[cid]['file']})")
            cards[cid] = {"file": rel, "links": card["links"]}

    known = set(cards)
    for cid, info in cards.items():
        for rel, targets in info["links"]:
            if rel not in ALLOWED_LINKS:
                errors.append(f"{info['file']}: связь '{rel}' вне закрытого списка")
            for t in targets:
                if t not in known:
                    errors.append(f"{info['file']}: висячая ссылка {rel} -> '{t}' (нет такой карточки)")

    print(f"Карточек: {len(cards)}  |  ошибок: {len(errors)}")
    for e in errors:
        print("  ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
