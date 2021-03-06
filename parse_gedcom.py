# -*- coding: utf-8 -*-

import collections

from graphviz import Digraph

class Record:
  def __init__(self, rec_id, rec_type, data):
    self.rec_id = rec_id
    self.rec_type = rec_type
    self.data = data
    self.sub_recs = []

  def GetFields(self, *fields):
    assert len(fields) > 0
    for record in self.sub_recs:
      if record.rec_type == fields[0]:
        if len(fields) == 1:
          return record.data
        else:
          return record.GetFields(*fields[1:])

def lex(ged_file):
  """Convert a .ged file into a list of Records."""
  root = Record(None, None, None)
  curr_for = [root]
  for line in ged_file:
    fields = line.split()
    if not fields:
      continue
    level = int(fields[0])
    if fields[1].startswith("@"):
      # Ex: 0 @I6@ INDI
      rec_id = fields[1]  # Ex: @I138@ or @F31@
      rec_type = fields[2]  # Ex: INDI or FAM
      data = " ".join(fields[3:])
    else:
      # Ex: 2 DATE 13 Dec 1985
      rec_id = None
      rec_type = fields[1]  # Ex: NAME, DATE, PLAC, CHIL, ...
      data = " ".join(fields[2:])
    this_rec = Record(rec_id, rec_type, data)

    # Find which record this is a sub-record of.
    parent = curr_for[int(level)]
    # Add as sub-record.
    parent.sub_recs.append(this_rec)
    # Update curr_for so that future records can be nested beneath this one.
    curr_for[level + 1:] = [this_rec]

  return root.sub_recs


def date2year(date):
  if date:
    return date.split()[-1]

class Person:
  def __init__(self, record):
    self.record = record
    self.parents = []
    self.children = []

  def id(self):
    return self.record.rec_id

  def name(self):
    return unicode(self.record.GetFields("NAME").replace("/", ""), "utf-8")

  def sex(self):
    return self.record.GetFields("SEX")

  def birthdate(self):
    return self.record.GetFields("BIRT", "DATE")

  def deathdate(self):
    return self.record.GetFields("DEAT", "DATE")

  def __repr__(self):
    return "%s (%s - %s)" % (self.name().encode("ascii", "replace"),  # TODO: Remove ASCII encode.
                             date2year(self.birthdate()),
                             date2year(self.deathdate()))

def parse(records):
  """Convert a list of Records into a structured graph of people."""
  # Collect all people.
  people = {}
  for record in records:
    if record.rec_type == "INDI":
      assert record.rec_id not in people
      people[record.rec_id] = Person(record)
  # Link parents and children.
  for record in records:
    if record.rec_type == "FAM":
      # For this "family unit" collect all parents and all children.
      parents = []
      children = []
      for sub_rec in record.sub_recs:
        if sub_rec.rec_type in ("HUSB", "WIFE"):
          parents.append(sub_rec.data)
        elif sub_rec.rec_type == "CHIL":
          children.append(sub_rec.data)
        # Ignore MARR, DATE, PLAC, ...
      # Add parent/child relationships.
      for child_id in children:
        child = people[child_id]
        for parent_id in parents:
          parent = people[parent_id]
          child.parents.append(parent)
          parent.children.append(child)
  return people


def print_ahnentafel(start_person):
  """Print an Ahnentafel list for a given person."""
  # Note: We don't actually keep track of gender, so this basically assumes
  # that Fathers (HUSB) are always listed first in FAM records.
  todo = collections.deque()
  todo.append((1, start_person))
  while todo:
    index, person = todo.popleft()
    print index, person.name(), person.sex(), person.birthdate(), person.deathdate()
    for i, parent in enumerate(person.parents):
      todo.append((2 * index + i, parent))


def get_ancestors(person):
  ancestors = set([person])
  for parent in person.parents:
    ancestors.update(get_ancestors(parent))
  return ancestors

def get_descendants(person):
  descendants = set([person])
  for parent in person.children:
    descendants.update(get_descendants(parent))
  return descendants

def get_relatives(person):
  relatives = set()
  for person in get_ancestors(person):
    relatives.update(get_descendants(person))
  return relatives

def find_common_ancestors(person1, person2):
  a1 = get_ancestors(person1)
  a2 = get_ancestors(person2)
  return a1.intersection(a2)

def find_most_recent(common):
  """Find all "most recent common ancestors", i.e. common ancestors whose
  children are not also common ancestors."""
  recent = set()
  for person in common:
    if not common.intersection(set(person.children)):
      recent.add(person)
  return recent

def find_mrca(person1, person2):
  return find_most_recent(find_common_ancestors(person1, person2))


def get_ancestor_lines(start_person):
  todo = collections.deque()
  todo.append((start_person, [start_person]))
  ancestor_lines = collections.defaultdict(list)
  while todo:
    person, line = todo.popleft()
    ancestor_lines[person].append(line)
    for parent in person.parents:
      todo.append((parent, line + [parent]))
  return ancestor_lines

def find_relationship(person1, person2):
  """Find all independent relationships between two people.
  Return type is a:
  * list with one item per MRCA of
  * pairs (one person1->MRCA, one for person2->MRCA) of
  * lists of all lines from person#->MRCA (typically 1, but can be more with
    endogamy, pedigree collapse or cousin marriage in general)
  """
  lines1 = get_ancestor_lines(person1)
  lines2 = get_ancestor_lines(person2)
  mrcas = find_most_recent(set(lines1).intersection(set(lines2)))

  relationships = []
  for anc in mrcas:
    relationships.append((lines1[anc], lines2[anc]))
  return relationships

def people2dot(people, dot_name):
  """Convert a collection of people into a DOT file showing relationships."""
  dot = Digraph(name=dot_name)

  for person in people:
    dot.node(person.id(), label=person.name())

  for person in people:
    for parent in person.parents:
      if parent in people:
        dot.edge(parent.id(), person.id())

  dot.view()

def relationships2people(relationships):
  people = set()
  for mrca in relationships:
    for person_mrca in mrca:
      for line in person_mrca:
        people.update(line)
  return people

def draw_relationships(person1, person2):
  # Collect set of all people between person1 and person2.
  people = relationships2people(find_relationship(person1, person2))
  people2dot(people, "%s_%s" % (person1.name(), person2.name()))


def find_person(name, people):
  for person in people.values():
    if person.name() == name:
      return person
  raise Exception, ("No person named %s" % name)

def find_prefix(prefix, people):
  filtered = []
  for person in people.values():
    if person.name().startswith(prefix):
      filtered.append(person)
  return filtered


def subset_dna(people):
  """Filter people so that it only includes people who are directly on
  relationship links between the home person (prefixed with 🏠) and
  all DNA matches (prefixed with 🔬)."""
  home_person, = find_prefix(u"🏠", people)
  dna_matches = find_prefix(u"🔬", people)

  filtered_people = set()
  for match in dna_matches:
    filtered_people.update(relationships2people(find_relationship(home_person,
                                                                  match)))
  return filtered_people

def filter_relatives(people, filter_person):
  """Filter people to only include relatives of filter_person."""
  return get_relatives(filter_person).intersection(people)

def find_roots(people):
  """Find who has no parents (root ancestors)."""
  filtered_people = set()
  for person in people:
    if not set(person.parents).intersection(people):
      filtered_people.add(person)
  return filtered_people

def find_not_in(people, filter):
  """Find minimum people in |people| not in |filter|."""
  new_people = set()
  for person in people.intersection(filter):
    new_people.update(set(person.parents) - filter)
    if len(person.parents) < 2:
     new_people.add("[Unknown parent(s) of %r]" % person)
  return new_people


import pprint
import sys
ged_file = file(sys.argv[1])

records = lex(ged_file)
people = parse(records)
home_person, = find_prefix(u"🏠", people)

# Find all relationships between two people:
#pprint.pprint(find_relationship(people[id1], people[id2]))
# Draw them:
#draw_relationships(find_person(name1, people),
#                   find_person(name2, people))

# Make a DOT graph of all people in GEDCOM:
#people2dot(people.values(), "all")

# Make a DOT graph only people allong DNA relationships:
name = unicode(sys.argv[2])
people2dot(filter_relatives(subset_dna(people),
                            find_person(name, people)),
           name)

# Find all DNA MRCAs (MRCAs between home person and a DNA match
# who doesn't have an ancestor who's also an MRCA for another match)
pprint.pprint(find_roots(subset_dna(people)))

# Find all ancestors in GEDCOM which are not DNA connected.
#pprint.pprint(find_not_in(get_ancestors(home_person),
#                          subset_dna(people)))

# Find all brick walls.
#pprint.pprint(find_roots(get_ancestors(home_person)))
