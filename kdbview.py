from kdbxtool import Database
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
import argparse
import pyperclip
import os
import getpass

c = Console()

def parse_args():
    parser = argparse.ArgumentParser(description="Interactive KeePass (.kdbx) shell")
    parser.add_argument(
        "db",
        nargs="?",
        default=None,
        help="Path to the .kdbx database file",
    )
    parser.add_argument(
        "-p",
        "--password",
        default=None,
        help="Database password (prompts securely if not provided)",
    )
    parser.add_argument(
        "-c",
        "--create",
        action="store_true",
        help="Create a new database",
    )
    args = parser.parse_args()

    if not args.db and not args.create:
        parser.print_help()
        parser.exit()

    return args

def resolve_path(start, target):
    """
    Examples:
        2
        2/3
        group
        grub/subgroup
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


def create_db(filepath: str | Path, password: str) -> str:
    filepath = Path(filepath).expanduser()

    if filepath.suffix.lower() != ".kdbx":
        filepath = filepath.with_suffix(".kdbx")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    if filepath.exists():
        raise FileExistsError(f"Database already exists: {filepath}")

    db = Database.create(
        password=password,
        database_name=filepath.stem,
    )

    db.save(str(filepath))

    c.print(f"[green]Database created:[/] {filepath}")

    return str(filepath)


args = parse_args()
db_path = args.db
db_password = args.password

try:
    if args.create:
        if not db_path:
            c.print("[green]Enter file path \\[./kdbxview-db.kdbx]:[/] ", end="")
            db_path = input().strip() or "./kdbxview-db.kdbx"
        if db_password is None:
            db_password = getpass.getpass("Database password: ")
        db_path = create_db(db_path, db_password)

    elif not os.path.exists(db_path):
        c.print(f"[yellow]Database not found:[/] {db_path}")
        c.print("Would you like to create new db? \\[Y/n]: ", end="")
        c_chall = input().strip() or "Y"

        if c_chall.lower().startswith("y"):
            c.print(f"[green]Enter file path \\[{db_path}]:[/] ", end="")
            c_dpath = input().strip() or db_path
            if db_password is None:
                db_password = getpass.getpass("Database password: ")
            db_path = create_db(c_dpath, db_password)
        else:
            raise FileNotFoundError(db_path)

    if db_password is None:
        db_password = getpass.getpass("Database password: ")

    with Database.open(
        db_path,
        password=db_password,
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

                    current.create_entry(
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

                    current.create_subgroup(name)

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
                        f"delete {getattr(obj,'name',getattr(obj,'title','item'))}? [y/N]: "
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

                elif action == "debug":

                    import inspect

                    print("add_entry      :", inspect.signature(current.add_entry))
                    print("create_entry   :", inspect.signature(current.create_entry))
                    print("add_subgroup   :", inspect.signature(current.add_subgroup))
                    print("create_subgroup:", inspect.signature(current.create_subgroup))

                else:
                    c.print("[red]unknown command[/]")

            except Exception as e:
                c.print(f"[red]{e}[/]")

except FileExistsError as e:
    c.print(f"[red]{e}[/]")

except FileNotFoundError as e:
    c.print(f"[red]Database not found:[/] {e}")

except Exception as e:
    c.print(
        "[red]Failed to open database. "
        f"Wrong password or invalid KDBX file.[/] {e}"
    )
