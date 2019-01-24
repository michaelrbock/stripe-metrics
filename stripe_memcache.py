from google.appengine.api import memcache

import logging
import stripe  # Official API client library.
import stripe_stats
import time

# Don't do this in production.
stripe.api_key = 'sk_test_nP2vuMlDAnxDttwjssMCcqKs'


def get_customer_email(customer_id):
  """Gets customer email address via customer_id from memcache or Stripe."""
  email = memcache.get(customer_id)
  if email:
    return email
  customer = stripe.Customer.retrieve(customer_id)
  memcache.set(customer_id, customer.email)
  return customer.email


def get_charges(offset_id):
  """Gets up to 100 charges starting at offset_id, from memcahce or Stripe."""
  offset_id_key = str(offset_id)
  charges = memcache.get(offset_id_key)
  if charges:
    return charges
  charges = stripe.Charge.list(limit=100, starting_after=offset_id)
  memcache.set(offset_id_key, charges)
  return charges


def cache_all_data():
  """Computes and caches all aggregated stripe stats data. Used by cron."""
  start = time.time()

  memcache.set('sorted_customer_ids_by_charges',
               stripe_stats.get_customers_sorted_by_charges())
  memcache.set('sorted_adjectives_by_charges',
               stripe_stats.get_adjectives_sorted_by_charges())

  end = time.time()
  logging.info(str(end - start) + 's taken.')


def cache_next_charge_data():
  """DEPRECATED.

  Backup method to cache_all_data(), in case that takes too long to finish in
  under 60s (GAE cron limit), but currently unused. Splits up calls to charges
  and does one per cron, aggregating results each time.
  """
  start = time.time()
  offset_id = memcache.get('last_offset_id')
  seen_ids = memcache.get('seen_ids')
  if seen_ids is None:
    seen_ids = set()

  customer_id_to_charges = memcache.get('customer_id_to_charges')
  if customer_id_to_charges is None:
    customer_id_to_charges = {}

  adjective_to_charges = memcache.get('adjective_to_charges')
  if adjective_to_charges is None:
    adjective_to_charges = {}

  offset_id = offset_id if offset_id != 'DONE' else None
  charges = memcache.get(str(offset_id))
  if not charges:
    logging.info('Charges not in memcache, getting from API.')
    charges = get_charges(offset_id)
    memcache.set(str(offset_id), charges)

  for charge in charges:
    if charge.id in seen_ids:
      logging.info("Ending early because we've seen these charges already")
      return
    seen_ids.add(charge.id)
    offset_id = charge.id
    if not charge.customer:
      continue
    if charge.customer in customer_id_to_charges:
      customer_id_to_charges[charge.customer] += charge.amount
    else:
      customer_id_to_charges[charge.customer] = charge.amount
    if not charge.description:
      continue
    adjective = stripe_stats.parse_adjective_from_description(
        charge.description)
    if adjective in adjective_to_charges:
      adjective_to_charges[adjective] += charge.amount
    else:
      adjective_to_charges[adjective] = charge.amount
  if not charges.has_more:
    # Start over looking for more charges.
    offset_id = None

  memcache.set('last_offset_id', offset_id)
  memcache.set('seen_ids', seen_ids)
  memcache.set('customer_id_to_charges', customer_id_to_charges)
  memcache.set(
      'sorted_customer_ids_by_charges',
      sorted(
          customer_id_to_charges.items(),
          key=lambda item: item[1],
          reverse=True))
  memcache.set('adjective_to_charges', adjective_to_charges)
  memcache.set(
      'sorted_adjectives_by_charges',
      sorted(
          adjective_to_charges.items(), key=lambda item: item[1], reverse=True))

  end = time.time()
  logging.info('Finished cron. There are now ' +
               str(len(customer_id_to_charges)) +
               ' customers in the cached dict.')
  logging.info('Next offset_id: ' + str(offset_id))
  logging.info(str(end - start) + 's taken.')
