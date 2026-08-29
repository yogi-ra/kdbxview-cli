from kdbxtool import Database
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
import pyperclip
import os
import getpass

load_dotenv()

DB_PATH = os.getenv("DB", r"file.kdbx")

c = Console()

def resolve_path(start, target):
    """
    Examples:
        2
        2/3
        cakrawala
        cakrawala/local
    """

    current = start

    parts = [p for p in str(target).split("/") if p]

    for part in parts:

        mapping = get_mapping(current)

        # numeric index
        if part.isdigit():

            idx = int(part)

            if idx not in mapping:
                return None

            _, obj = mapping[idx]
            current = obj

        else:

            found = None

            for g in current.subgroups:
                if g.name.lower() == part.lower():
                    found = g
                    break

            if found:
                current = found
                continue

            for e in current.entries:
                if (e.title or "").lower() == part.lower():
                    found = e
                    break

            if found:
                current = found
            else:
                return None

    return current

def path(grp):
    parts = []
    cur = grp

    while cur:
        if cur.name:
            parts.append(cur.name)
        cur = getattr(cur, "parent", None)

    return "/" + "/".join(reversed(parts))


def get_mapping(grp):
    mapping = {}
    i = 1

    for g in grp.subgroups:
        mapping[i] = ("group", g)
        i += 1

    for e in grp.entries:
        mapping[i] = ("cred", e)
        i += 1

    return mapping


def ls(grp):
    tbl = Table(title=path(grp))

    tbl.add_column("#", width=4)
    tbl.add_column("Type", width=10)
    tbl.add_column("Name")

    mapping = get_mapping(grp)

    for idx, (typ, obj) in mapping.items():

        if typ == "group":
            tbl.add_row(
                str(idx),
                "📁 DIR",
                obj.name
            )
        else:
            tbl.add_row(
                str(idx),
                "🔑 CRED",
                obj.title or "(untitled)"
            )

    c.print(tbl)

    return mapping


def show_entry(e, show_pass=True):
    c.print(f"[bold cyan]Title:[/] {e.title}")
    c.print(f"[bold cyan]Username:[/] {e.username}")

    if show_pass:
        c.print(f"[bold cyan]Password:[/] {e.password}")

    if getattr(e, "url", None):
        c.print(f"[bold cyan]URL:[/] {e.url}")

    if getattr(e, "notes", None):
        c.print(f"[bold cyan]Notes:[/] {e.notes}")


def build_tree(group, node):

    for g in group.subgroups:
        child = node.add(f"[cyan]📁 {g.name}")
        build_tree(g, child)

    for e in group.entries:
        node.add(f"[green]🔑 {e.title}")


try:

    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(DB_PATH)

    with Database.open(
        DB_PATH,
        password=os.getenv("PASS")
    ) as db:

        current = db.root_group

        c.print("[green]KeePass Shell[/]")
        c.print("type 'help'")

        while True:

            try:

                cmd = input(f"{path(current)}> ").strip()

                if not cmd:
                    continue

                parts = cmd.split()
                action = parts[0].lower()

                # ---------------- HELP ----------------

                if action == "help":
                    c.print("""
ls                      list current group
ls N                    list group by index
ls GROUP                list group by name

cd N                    enter group by index
cd GROUP                enter group by name
cd ..                   go back

pwd                     show current path

view N                  show credential
cat N                   alias of view

cp N                    copy password

new                     create credential
mkdir                   create subgroup

rm N                    delete item

search TEXT             search credentials

tree                    show entire tree

clear                   clear screen
cls                     clear screen

quit                    exit
""")

                # ---------------- QUIT ----------------

                elif action in ("quit", "exit", "q"):
                    break

                # ---------------- PWD ----------------

                elif action in ("pwd", "cwd"):
                    c.print(path(current))

                # ---------------- LS ----------------

                elif action in ("ls", "dir"):
                
                    if len(parts) == 1:
                        ls(current)
                        continue
                
                    obj = resolve_path(current, " ".join(parts[1:]))
                
                    if obj is None:
                        c.print("[red]not found[/]")
                        continue
                
                    if not hasattr(obj, "subgroups"):
                        c.print("[red]not a group[/]")
                        continue
                
                    ls(obj)

                # ---------------- CD ----------------

                elif action == "cd":

                    if len(parts) < 2:
                        c.print("[red]usage: cd GROUP[/]")
                        continue

                    target = " ".join(parts[1:])

                    if target == "..":
                        if current.parent:
                            current = current.parent
                        continue

                    obj = resolve_path(current, target)

                    if obj is None:
                        c.print("[red]path not found[/]")
                        continue

                    if not hasattr(obj, "subgroups"):
                        c.print("[red]not a group[/]")
                        continue

                    current = obj

                # ---------------- VIEW ----------------

                elif action in ("view", "cat"):
                
                    if len(parts) < 2:
                        c.print("[red]usage: view PATH[/]")
                        continue
                
                    obj = resolve_path(current, parts[1])
                
                    if obj is None:
                        c.print("[red]not found[/]")
                        continue
                
                    if not hasattr(obj, "password"):
                        c.print("[red]not a credential[/]")
                        continue
                
                    show_entry(obj)

                # ---------------- COPY ----------------

                elif action == "cp":
                
                    if len(parts) < 2:
                        c.print("[red]usage: cp PATH[/]")
                        continue
                
                    obj = resolve_path(current, parts[1])
                
                    if obj is None:
                        c.print("[red]not found[/]")
                        continue
                
                    if not hasattr(obj, "password"):
                        c.print("[red]not a credential[/]")
                        continue
                
                    pyperclip.copy(obj.password)
                
                    c.print("[green]password copied[/]")

                # ---------------- NEW ENTRY ----------------

                elif action == "new":

                    title = input("Title: ")
                    username = input("Username: ")
                    password = getpass.getpass("Password: ")
                    url = input("URL: ")

                    current.add_entry(
                        title=title,
                        username=username,
                        password=password,
                        url=url,
                    )

                    db.save()

                    c.print("[green]saved[/]")

                # ---------------- NEW GROUP ----------------

                elif action == "mkdir":

                    name = input("Group name: ").strip()

                    current.add_subgroup(name)

                    db.save()

                    c.print("[green]group created[/]")

                # ---------------- REMOVE ----------------

                elif action == "rm":

                    if len(parts) < 2:
                        c.print("[red]usage: rm N[/]")
                        continue

                    idx = int(parts[1])

                    mapping = get_mapping(current)

                    if idx not in mapping:
                        c.print("[red]invalid index[/]")
                        continue

                    typ, obj = mapping[idx]

                    confirm = input(
                        f"delete {getattr(obj,'name',getattr(obj,'title','item'))}? [y/N] "
                    )

                    if confirm.lower() != "y":
                        continue

                    if typ == "cred":
                        current.remove_entry(obj)

                    elif typ == "group":
                        current.remove_subgroup(obj)

                    db.save()

                    c.print("[green]deleted[/]")

                # ---------------- SEARCH ----------------

                elif action == "search":

                    if len(parts) < 2:
                        continue

                    query = " ".join(parts[1:]).lower()

                    tbl = Table(title=f"Search: {query}")
                    tbl.add_column("Title")
                    tbl.add_column("Username")
                    tbl.add_column("Path")

                    count = 0

                    for e in db.iter_entries():

                        text = " ".join([
                            str(e.title or ""),
                            str(e.username or ""),
                            str(e.url or ""),
                        ]).lower()

                        if query in text:

                            entry_path = (
                                path(e.parent)
                                if hasattr(e, "parent") and e.parent
                                else "-"
                            )

                            tbl.add_row(
                                e.title or "",
                                e.username or "",
                                entry_path,
                            )

                            count += 1

                    c.print(tbl)
                    c.print(f"[green]{count} result(s)[/]")

                # ---------------- TREE ----------------

                elif action == "tree":

                    root = Tree(
                        f"[bold yellow]{db.root_group.name}"
                    )

                    build_tree(
                        db.root_group,
                        root
                    )

                    c.print(root)

                # ---------------- CLEAR ----------------

                elif action in ("clear", "cls"):

                    os.system(
                        "cls" if os.name == "nt" else "clear"
                    )

                    c.print("[green]KeePass Shell[/]")
                    c.print("type 'help'")

                else:
                    c.print("[red]unknown command[/]")

            except Exception as e:
                c.print(f"[red]{e}[/]")

except FileNotFoundError:
    c.print(f"[red]Database not found:[/] {DB_PATH}")

except Exception:
    c.print(
        "[red]Failed to open database. Wrong password or invalid KDBX file.[/]"
    )