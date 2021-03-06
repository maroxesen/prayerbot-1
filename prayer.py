#!/usr/bin/env python2
# -*- coding: UTF-8 -*-

import json
import facebook.utils as utils
import tools.systools as systools
from dbms.rdb import db
from dbms.models import Intent
from translations.user import user_gettext

displayed_prayers_limit = 5


##TODO: remove test
#from db.storage import PostgresStorage
#storage = PostgresStorage()
#storage.test()
##END of block to remove

class PrayerWebhook(object):
    @staticmethod
    def handle_message(sender, message):
        response = None
        text = message['text'].encode('utf-8')
        lower_text = text.lower()
        sender_id = sender['id']
        # initialized_prayers = db.fetch_history({"user_id": sender_id, "description": ""})
        initialized_prayers = Intent.query.filter_by(user_id = sender_id, description = "").all()
        if initialized_prayers != []:
            prayer = initialized_prayers[0]
            response_message = utils.response_buttons(
                user_gettext(sender_id, u"You requested a prayer for: %(value)s?", value=text),
                [
                    {
                        "type":"postback",
                        "title": user_gettext(sender_id, u"Yes"),
                        "payload": json.dumps({"user_event": "update_prayer", "prayer_id": prayer.id, "description": text})
                    },
                    {
                        "type":"postback",
                        "title": user_gettext(sender_id, u"No"),
                        "payload": json.dumps({"user_event": "delete_prayer", "prayer_id": prayer.id})
                    },
                ]
            )
            response = json.dumps({
                'recipient': { 'id' : sender_id },
                'message': response_message
            })
        elif lower_text in user_gettext(sender_id, u'help') or user_gettext(sender_id, u'pray') in lower_text:
            # commited_prayers = db.fetch_history({"commiter_id": sender_id})
            commited_prayers = Intent.query.filter_by(commiter_id = sender_id)
            options = [
                {
                    "type":"postback",
                    "title": user_gettext(sender_id, u"Please pray for me"),
                    "payload": json.dumps({"user_event": "pray_for_me"})
                },
                {
                    "type":"postback",
                    "title": user_gettext(sender_id, u"I want to pray"),
                    "payload": json.dumps({"user_event": "want_to_pray"})
                },
            ]
            if commited_prayers != []:
                options.append({
                    "type":"postback",
                    "title": user_gettext(sender_id, u"Who do I pray for?"),
                    "payload": json.dumps({"user_event": "prayers"})
                })
            response_message = utils.response_buttons(
                user_gettext(sender_id, u"Please choose what do you need?"),
                options
            )
            response = json.dumps({
                'recipient': { 'id' : sender_id },
                'message': response_message
            })
        elif text == 'info':
            resp_text = systools.system_info()
            response_message = utils.response_text("Version: " + resp_text)
            response = json.dumps({
                'recipient': { 'id' : sender_id },
                'message': response_message
            })
        else:
            response_message = utils.response_text(user_gettext(sender_id, u"Sorry but I don't understand you.\nType 'help' to get additional information."))
            response = json.dumps({
                'recipient': { 'id' : sender_id },
                'message': response_message
            })
        return response

    @staticmethod
    def handle_postback(sender, postback):
        payload = json.loads(postback['payload'])
        sender_id = sender['id']
        if 'user_event' in payload:
            event_type = payload['user_event']
            callbacks = PrayerWebhook.handle_user_event(sender_id, event_type, payload)
        elif 'prayer_event' in payload:
            event_type = payload['prayer_event']
            callbacks = PrayerWebhook.handle_prayer_event(sender_id, event_type, payload)
        response_callbacks = map(map_callback, callbacks.items())
        return response_callbacks

    @staticmethod
    def handle_user_event(sender_id, event_type, payload):
        if event_type == 'update_prayer':
            # TODO: update prayer in DB
            id_value = payload["prayer_id"]
            description_value = payload["description"]
            #db.update_description(id_value, description_value)
            intent = Intent.query.filter_by(id = id_value).first()
            intent.description = description_value
            db.session.commit()
            return {
                sender_id : utils.response_text(user_gettext(sender_id, u"You'll be notified when somebody wants to pray for you")),
            }
        elif event_type == 'delete_prayer':
            # TODO: delete prayer from DB
            id_value = payload["prayer_id"]
            #db.delete(id_value)
            intent = Intent.query.filter_by(id = id_value).first()
            db.session.delete(intent)
            db.session.commit()
            return {
                sender_id : utils.response_text(user_gettext(sender_id, u"I've deleted a prayer request")),
            }
        elif event_type == 'pray_for_me':
            # data_line = dict(
            #     user_id=sender_id,
            #     commiter_id="",
            #     ts=1234,
            #     description="",
            #     )
            # db.insert_row(data_line)
            intent = Intent(sender_id, "")
            intent.ts = 1234
            db.session.add(intent)
            db.session.commit()
            response_message = utils.response_buttons(
                user_gettext(sender_id, u"What is your prayer request?"),
                [
                    {
                        "type":"postback",
                        "title":"Odwołaj modlitwę", #nie ma wersji angielskiej
                        "payload": json.dumps({"user_event": "delete_prayer"})
                    }
                ])
            return {
                sender_id : response_message
            }

        elif event_type == 'want_to_pray':
            # prayers = db.fetch_history({"commiter_id": ""}, displayed_prayers_limit)
            prayers = Intent.query.limit(displayed_prayers_limit).all()
            #print("Fetched prayers: " + json.dumps(prayers))
            prayer_elements = map(map_prayer, prayers)
            return {
                sender_id : utils.response_elements(prayer_elements),
            }
        elif event_type == 'prayers':
            # commited_prayers = db.fetch_history({"commiter_id": sender_id})
            commited_prayers = Intent.query.filter_by(commiter_id = sender_id)
            prayer_elements = map(map_said_prayer, commited_prayers)
            if prayer_elements == []:
                return {
                    sender_id : utils.response_text(user_gettext(sender_id, u"There're no prayer requests")),
                }
            else:
                return {
                    sender_id : utils.response_elements(prayer_elements),
                }

    @staticmethod
    def handle_prayer_event(sender_id, event_type, payload):
        user_id = payload['user_id']
        prayer_id = payload['prayer_id']
        user_name = utils.user_name(user_id)
        sender_name = utils.user_name(sender_id)
        # prayer = db.fetch(prayer_id)
        prayer = Intent.query.filter_by(id = prayer_id).one_or_none()
        prayer_description = prayer.description.encode("utf-8")

        if event_type == 'i_pray':
            # db.update_commiter(prayer_id, sender_id)
            prayer.commiter_id=sender_id
            db.session.commit()
            return {
                sender_id : utils.response_text(user_gettext(sender_id, u"You're subscribed for the prayer request from user %(name)s", name=user_name)),
                user_id : utils.response_text(user_gettext(user_id, u"User %(name)s will be praying in your following request: %(desc)s", name=sender_name, desc=prayer_description)),
            }
        elif event_type == 'did_pray':
            # db.delete(prayer_id)
            db.session.delete(prayer)
            db.session.commit()
            return {
                user_id : utils.response_text(user_gettext(user_id, 'User %(name)s has prayed in your request: %(desc)s', name=sender_name, desc=prayer_description)),
                sender_id : utils.response_text(user_gettext(sender_id, 'User %(name)s has been notified that you\'ve prayed for him/her. Thank you', name=user_name)),
            }
        elif event_type == 'send_message':
            return {
                user_id : utils.response_text(user_gettext(user_id, 'User %(name)s wants to ensure you about his prayer in the following request: %(desc)s', name=sender_name, desc=prayer_description)),
                sender_id : utils.response_text(user_gettext(sender_id, 'User %(name)s has been ensured that you pray for him', name=user_name)),
            }
        elif event_type == 'give_up':
            # db.update_commiter(prayer_id, '')
            prayer.commiter_id=''
            db.session.commit()
            return {
                sender_id : utils.response_text(user_gettext(sender_id, 'Thank you for your will of praying. User %(name)s won\'t be notified about you giving up.', name=user_name)),
            }

def map_callback(callback):
    sender_id = callback[0]
    response_message = callback[1]
    return json.dumps({
        'recipient': { 'id' : sender_id },
        'message': response_message
    })

def map_prayer(prayer):
    user_id = prayer.user_id
    return {
        "title": utils.user_name(user_id),
        "subtitle": prayer.description,
        "buttons": [
            {
                "type": "postback",
                "title": user_gettext(user_id, "I am praying"),
                "payload": json.dumps({"prayer_event": "i_pray", "prayer_id": prayer.id, "user_id": user_id})
            }
        ],
        "image_url": utils.get_img_url(user_id)
    }

def map_said_prayer(prayer):
    user_id = prayer.user_id
    return {
        "title": utils.user_name(user_id),
        "subtitle": prayer.description,
        "buttons": [
            {
                "type": "postback",
                "title": user_gettext(user_id, "I've prayed"),
                "payload": json.dumps({"prayer_event": "did_pray", "prayer_id": prayer.id, "user_id": user_id})
            },
            {
                "type": "postback",
                "title": user_gettext(user_id, "Ensure about your prayer"),
                "payload": json.dumps({"prayer_event": "send_message", "prayer_id": prayer.id, "user_id": user_id})
            },
            {
                "type": "postback",
                "title": user_gettext(user_id, "Stop your prayer"),
                "payload": json.dumps({"prayer_event": "give_up", "prayer_id": prayer.id, "user_id": user_id})
            },
        ],
        "image_url": utils.get_img_url(user_id)
    }
