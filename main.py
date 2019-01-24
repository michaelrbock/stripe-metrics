from google.appengine.api import memcache
from google.appengine.api import urlfetch

import logging
import json
import stripe_memcache
import stripe_stats
import webapp2

# Don't do this in production.
_PAGE_ACCESS_TOKEN = 'EAAFJkmxLfR8BALsKFRZBxFZC1k6iYOTOpkTe9Xz0gG76slrqctMZCDYZA3MPMS7fZCZBvmotzkzRjPUmqi62uqAV4wHAlGZC9XtQh4vdsCVynTgZAZAVKl6fFZAH5Fin1UCRZASpXa09ViRHuI4Owr166iFeWgqcNUOtQVT070tPBaSDQZDZD'

# FB Messenger verification token.
_VERIFICATION_TOKEN = 'stripe_metrics_verification_token'

# Button payloads.
PAYLOAD_MAIN_MENU = '0'
PAYLOAD_TOP_CUSTOMERS = '1'
PAYLOAD_NEXT_CUSTOMERS = '2'
PAYLOAD_TOP_ADJECTIVES = '3'
PAYLOAD_NEXT_ADJECTIVES = '4'


class BaseHandler(webapp2.RequestHandler):

  def write(self, *a, **kw):
    self.response.out.write(*a, **kw)


class MainHandler(BaseHandler):

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.write('Hello')


class WebhookHandler(BaseHandler):

  def get(self):
    """Verifies our application to Facebook."""
    if (self.request.get('hub.mode') == 'subscribe' and
        self.request.get('hub.verify_token') == _VERIFICATION_TOKEN):
      logging.info('WEBHOOK_VERIFIED')
      self.write(self.request.get('hub.challenge'))

  def call_send_api(self, message_data):
    """Sends a generic message to FB Messenger API."""
    uri = ('https://graph.facebook.com/v2.6/me/messages?access_token=' +
           _PAGE_ACCESS_TOKEN)
    payload = json.dumps(message_data)
    result = urlfetch.fetch(
        uri,
        method='POST',
        payload=payload,
        headers={'Content-Type': 'application/json'})
    if result.status_code == 200:
      content = json.loads(result.content)
      logging.info(
          'Successfully sent generic message with id %s to recipient %s',
          content['recipient_id'], content['message_id'])
    else:
      logging.error('Unable to send message.')
      logging.error(result.status_code)
      logging.error(result.content)

  def send_text_message(self, recipient_id, text):
    """Sends a text message to recipient."""
    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': text
        }
    }
    self.call_send_api(message_data)

  def send_button_message(self, recipient_id, text, buttons):
    """Sends a message with given text and button options."""
    for button in buttons:
      button['type'] = 'postback'
    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'attachment': {
                'type': 'template',
                'payload': {
                    'template_type': 'button',
                    'text': text,
                    'buttons': buttons
                }
            }
        }
    }
    self.call_send_api(message_data)

  def received_authentication(self, event):
    """Ignore auth messages."""
    pass

  def send_main_menu(self, sender_id):
    """Send the main 'menu' for our chatbot app."""
    buttons = [{
        'title': 'See Top Customers',
        'payload': PAYLOAD_TOP_CUSTOMERS
    }, {
        'title': 'See Top Descriptions',
        'payload': PAYLOAD_TOP_ADJECTIVES
    }]
    self.send_button_message(
        sender_id,
        'Hi! Welcome to the Stripe Metrics chatbot for JupiterShop. Please '
        'select an option below to find out more about your business metrics:',
        buttons)

  def received_message(self, event):
    """Receives any text message from user, respond with main menu."""
    sender_id = event['sender']['id']
    recipient_id = event['recipient']['id']
    time_of_message = event['timestamp']
    message = event['message']

    logging.info('Received message for user %s and page %s at %d with message:',
                 sender_id, recipient_id, time_of_message)
    logging.info(str(message))

    if not message['text']:
      logging.error('Received an empty message.')
      return

    self.send_main_menu(sender_id)

  def received_delivery_confirmation(self, event):
    """Ignore delivery confirm messages from FB."""
    pass

  def send_next_5_customers(self, sender_id, offset=0):
    self.send_text_message(sender_id, 'Thinking....')
    customers_sorted_by_charges = memcache.get('sorted_customer_ids_by_charges')
    if customers_sorted_by_charges is None:
      customers_sorted_by_charges = stripe_stats.get_sorted_charges_by_customer_id(
      )
    if offset >= len(customers_sorted_by_charges):
      self.send_text_message(sender_id, 'That is all the top customers!')
      self.send_main_menu(sender_id)
    text = [
        'Here are your top %d to %d customers sorted by spending:\n' %
        (offset + 1, offset + 5)
    ]
    for i, customer_tuple in enumerate(
        customers_sorted_by_charges[offset:offset + 5]):
      customer, spend = customer_tuple
      email = stripe_memcache.get_customer_email(customer)
      text.append(
          str(offset + i + 1) + '. ' + email + ' spent ' +
          stripe_stats.cents_to_formatted_dollars(spend) + '\n')
    self.send_text_message(sender_id, ''.join(text))
    buttons = [{
        'title': 'See next 5 customers',
        'payload': PAYLOAD_NEXT_CUSTOMERS
    }, {
        'title': 'Main Menu',
        'payload': PAYLOAD_MAIN_MENU
    }]
    self.send_button_message(sender_id, 'What would you like to do next?',
                             buttons)
    memcache.set(sender_id + '_top_customer_offset', offset + 5)

  def send_next_5_adjectives(self, sender_id, offset=0):
    """TODO: this function and above are about the same, merge into one."""
    self.send_text_message(sender_id, 'Thinking....')
    adjectives_sorted_by_charges = memcache.get('sorted_adjectives_by_charges')
    if adjectives_sorted_by_charges is None:
      adjectives_sorted_by_charges = stripe_stats.get_adjectives_sorted_by_charges(
      )
      memcache.set('sorted_adjectives_by_charges', adjectives_sorted_by_charges)
    if offset >= len(adjectives_sorted_by_charges):
      self.send_text_message(sender_id, 'That is all the top descriptions!')
      self.send_main_menu(sender_id)
    text = [
        'These are the to %d to %d item descriptions/adjectives which made the '
        'most money:\n' % (offset + 1, min(len(adjectives_sorted_by_charges),
                           offset + 5))
    ]
    for i, adjective_tuple in enumerate(
        adjectives_sorted_by_charges[offset:offset + 5]):
      adjective, spend = adjective_tuple
      text.append(
          str(offset + i + 1) + '. "' + adjective + '" items sold for ' +
          stripe_stats.cents_to_formatted_dollars(spend) + '\n')
    self.send_text_message(sender_id, ''.join(text))
    buttons = [{
        'title': 'See next 5',
        'payload': PAYLOAD_NEXT_ADJECTIVES
    }, {
        'title': 'Main Menu',
        'payload': PAYLOAD_MAIN_MENU
    }]
    self.send_button_message(sender_id, 'What would you like to do next?',
                             buttons)
    memcache.set(sender_id + '_top_adjective_offset', offset + 5)

  def received_postback(self, event):
    """Handle 'postback' message, when the user clicks a button."""
    sender_id = event['sender']['id']
    recipient_id = event['recipient']['id']
    time_of_postback = event['timestamp']

    payload = event['postback']['payload']

    logging.info(
        'Received postback for user %s and page %s with payload (%s)'
        ' at %d', sender_id, recipient_id, payload, time_of_postback)

    if payload == PAYLOAD_MAIN_MENU:
      self.send_main_menu(sender_id)
    elif payload == PAYLOAD_TOP_CUSTOMERS:
      self.send_next_5_customers(sender_id)
    elif payload == PAYLOAD_NEXT_CUSTOMERS:
      offset = memcache.get(sender_id + '_top_customer_offset')
      if offset is None:
        offset = 0
      self.send_next_5_customers(sender_id, offset)
    elif payload == PAYLOAD_TOP_ADJECTIVES:
      self.send_next_5_adjectives(sender_id)
    elif payload == PAYLOAD_NEXT_ADJECTIVES:
      offset = memcache.get(sender_id + '_top_adjective_offset')
      if offset is None:
        offset = 0
      self.send_next_5_adjectives(sender_id, offset)

  def post(self):
    """Main routing for POST requests received from Messenger."""
    request_obj = json.loads(self.request.body)
    logging.info(str(request_obj))
    if request_obj['object'] == 'page':
      for entry in request_obj['entry']:
        time = entry['time']

      # Get the webhook event. entry.messaging is an array, but will only ever
      # contain one event, so get index 0.
      messaging_event = entry['messaging'][0]
      if 'optin' in messaging_event:
        self.received_authentication(messaging_event)
      elif 'message' in messaging_event:
        self.received_message(messaging_event)
      elif 'delivery' in messaging_event:
        self.received_delivery_confirmation(messaging_event)
      elif 'postback' in messaging_event:
        self.received_postback(messaging_event)
      else:
        logging.error('Webhook received unknown messaging_event: ' +
                      str(messaging_event))


class CronHandler(BaseHandler):

  def get(self):
    stripe_memcache.cache_all_data()


app = webapp2.WSGIApplication([('/', MainHandler), ('/cron', CronHandler),
                               ('/webhook', WebhookHandler)],
                              debug=True)
