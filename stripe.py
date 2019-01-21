from collections import defaultdict
import stripe
import time


def get_charges_by_customer():
  customers = defaultdict(int)  # { id : total purchased amount }
  offset_id = None

  # debug
  api_calls = 0
  num_charges = 0

  while True:
    charges = stripe.Charge.list(limit=100, starting_after=offset_id)
    api_calls += 1
    for charge in charges:
      num_charges += 1
      offset_id = charge.id
      if not charge.customer:
        continue
      customers[charge.customer] += charge.amount
    if not charges.has_more:
      break

  # debug
  print('API Calls: ', api_calls)
  print('Total # of charges: ', num_charges)

  return customers


def get_customer_email(customer_id):
  customer = stripe.Customer.retrieve(customer_id)
  return customer.email


def main():
  stripe.api_key = "sk_test_nP2vuMlDAnxDttwjssMCcqKs"

  start = time.time()
  customer_to_charges = get_charges_by_customer()
  customers_sorted_by_charges = sorted(
    customer_to_charges.items(), key=lambda item: item[1], reverse=True)
  print('Top customer emails: ')
  print(get_customer_email(customers_sorted_by_charges[0][0]))
  print(get_customer_email(customers_sorted_by_charges[1][0]))
  print(get_customer_email(customers_sorted_by_charges[2][0]))
  print(get_customer_email(customers_sorted_by_charges[3][0]))
  print(get_customer_email(customers_sorted_by_charges[4][0]))
  end = time.time()

  print(end - start, 's taken!')


if __name__ == '__main__':
  main()
