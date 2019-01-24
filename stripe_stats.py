from __future__ import division  # GAE is still on Python 2.
from collections import defaultdict

import logging
import stripe_memcache
import time


def get_all_charges():
  """Gets and returns all charges available via the Stripe API."""
  all_charges = []
  offset_id = None

  # Debug variables.
  api_calls = 0

  while True:
    charges = stripe_memcache.get_charges(offset_id)
    logging.info('Got this many charges: ' + str(len(charges.data)))
    api_calls += 1
    for charge in charges:
      offset_id = charge.id
      all_charges.append(charge)
    if not charges.has_more:
      break

  logging.info('API Calls: ' + str(api_calls))

  return all_charges


def get_customers_sorted_by_charges():
  """Returns list of (customer id, total charge amount) tuples sorted by the latter."""
  # { id : total purchased amount in cents }
  customer_to_charges = defaultdict(int)
  charges = get_all_charges()
  for charge in charges:
    if not charge.customer:
      continue
    customer_to_charges[charge.customer] += charge.amount
  return sorted(
    customer_to_charges.items(), key=lambda item: item[1], reverse=True)


def parse_adjective_from_description(description):
  """Returns the adjective (first word) in a multi-word description, e.g.
     'Refined Wooden Bacon' -> 'Refined'."""
  return description.split(' ')[0]


def get_adjectives_sorted_by_charges():
  """Returns a list of (adjective, total charge amount) tuples sorted by the
     latter.

  TODO: this function and above are about the same. Merge into one.
  """
  # { adjective: total purchase amount in cents }
  adjective_to_charges = defaultdict(int)
  charges = get_all_charges()
  for charge in charges:
    if not charge.description:
      continue
    adjective = parse_adjective_from_description(charge.description)
    adjective_to_charges[adjective] += charge.amount
  return sorted(
    adjective_to_charges.items(), key=lambda item: item[1], reverse=True)


def cents_to_formatted_dollars(cents):
  """Returns a string of formatted money from int cents, e.g. 499 -> '$4.99'"""
  return '${:0.2f}'.format(cents / 100.)
