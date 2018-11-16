import discord as dc
import numpy as np
import asyncio, queue, threading, boto3
rands = np.random.binomial(1, 0.01, 1000)


class Client:

    TOKEN = "NTEyMzM0NjE4MDcxMTM4MzA1.Ds4W8g.OFzmPZ8u_qZ2Gt7IlvZO--N4Dt4"
    PREFIX = dict()
    disc_client = dc.Client()
    client_started = False
    players = dict()
    voice_channels = dict()
    text_channels = dict()
    lock = asyncio.Lock()
    polly_client = boto3.Session(
        aws_access_key_id="AKIAIPFMNB63TBTFTSSA",
        aws_secret_access_key="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",
        region_name='us-west-2').client('polly')
    COMMAND_LIST = [
        'sesh',
        'leave',
        'sleep',
        'setvc',
        'settc',
        'help',
        'prefix',
        'say'

    ]

    def __init__(self):
        if not Client.client_started:
            Client.client_started = True
            Client.disc_client.run(Client.TOKEN)

    @staticmethod
    def initialize_dicts():
        for server in Client.disc_client.servers:
            for channel in server.channels:
                Client.players[server.name] = None
                Client.text_channels[server.name] = None
                Client.PREFIX[server.name] = ';'
                if channel.name == "sesh":
                    Client.voice_channels[server.name] = channel
                else:
                    Client.voice_channels[server.name] = None

    @staticmethod
    @disc_client.event
    async def on_ready():
        print('Logged in as')
        print(Client.disc_client.user.name)
        print(Client.disc_client.user.id)
        print('------')
        Client.initialize_dicts()
    #     -------------------- ADD CHANNEL OVERRIDES HERE --------------------

    @staticmethod
    @disc_client.event
    async def on_message(message):
        if message.author.id == '290665707346329601':
            await Client.disc_client.send_message(message.channel, ':poop: :poop: {}'.format(message.author.mention))
            return
        if message.content.startswith(Client.PREFIX[message.server.name]) and \
                Client.text_channels[message.server.name] and \
                Client.text_channels[message.server.name] == message.channel.id:
            await Client.do_command(message)
        elif message.content.startswith(Client.PREFIX[message.server.name]) and not \
                Client.text_channels[message.server.name]:
            await Client.do_command(message)

    @staticmethod
    async def do_prefix(message, tokens):
        if len(tokens) > 1:
            await Client.disc_client.send_message(message.channel, 'command prefix is now {}'.format(tokens[1]))
            Client.PREFIX[message.server.name] = tokens[1]

    @staticmethod
    async def do_set_tc(message, tokens):
        if len(tokens) > 1:
            if tokens[1].lower() == 'none':
                Client.text_channels[message.server.name] = None
                await Client.disc_client.send_message(message.channel, "sounds good fam")
                return
            for channel in message.server.channels:
                if channel.name.lower() == tokens[1].lower():
                    await Client.disc_client.send_message(message.channel, "hey i'm gonna go chill at {} hmu there"
                                                          .format(channel.name))
                    Client.text_channels[message.server.name] = channel.id

    @staticmethod
    async def get_voice_client(message, server):
        if Client.voice_channels[server.name]:
            if not Client.disc_client.voice_client_in(server):
                await Client.disc_client.send_message(message.channel, "hey man wanna get high")
                voice = await Client.disc_client.join_voice_channel(Client.voice_channels[server.name])
                return voice
            else:
                await Client.disc_client.send_message(message.channel, "sorry i'm already seshing with the squad "
                                                                       "reach tho")
                return None
        else:
            await Client.disc_client.send_message(message.channel, "let me reach the crib u piece of shit use {}setvc "
                                                                   "<channel>".format(Client.PREFIX[server.name]))
            return None


    @staticmethod
    async def do_sesh(message, tokens):
        voice_client = await Client.get_voice_client(message, message.server)
        if voice_client:
            player = await voice_client.create_ytdl_player('https://www.youtube.com/watch?v=kJa2kwoZ2a4')
            Client.players[message.server.name] = player
            player.start()

    @staticmethod
    async def do_leave(message, tokens):
        if Client.disc_client.voice_client_in(message.server):
            await Client.disc_client.send_message(message.channel, "gtg my moms pissed again")
            if Client.players[message.server.name]:
                player = Client.players[message.server.name]
                player.stop()
                del player
                await Client.disc_client.voice_client_in(message.server).disconnect()
                Client.players[message.server.name] = None
            else:
                await Client.disc_client.voice_client_in(message.server).disconnect()

    @staticmethod
    async def do_say(message, tokens):
        VOICE = "Justin"
        if len(tokens) > 1:
            if Client.disc_client.voice_client_in(message.server):
                Client.players[message.server.name].stop()
                Client.players[message.server.name] = None
                voice_client = Client.disc_client.voice_client_in(message.server)
                polly_response = Client.polly_client.synthesize_speech(VoiceId=VOICE, OutputFormat='mp3',
                                                                      Text=' '.join(tokens[1:]))

                temp_file = open("temp.mp3", "wb")
                temp_file.write(polly_response['AudioStream'].read())
                temp_file.close()
                player = voice_client.create_ffmpeg_player("temp.mp3", use_avconv=True)
                Client.players[message.server.name] = player
                player.start()
                return
            else:
                if Client.voice_channels[message.server.name]:
                    voice_client = await Client.disc_client.join_voice_channel(Client.voice_channels[message.server.name])
                    polly_response = Client.polly_client.synthesize_speech(VoiceId=VOICE, OutputFormat='mp3',
                                                                           Text=' '.join(tokens[1:]))

                    temp_file = open("temp.mp3", "wb")
                    temp_file.write(polly_response['AudioStream'].read())
                    temp_file.close()
                    player = voice_client.create_ffmpeg_player("temp.mp3", use_avconv=True)
                    Client.players[message.server.name] = player
                    player.start()
                    return

    @staticmethod
    async def do_command(message):
        tokens = message.content.rsplit()
        command = tokens[0][len(Client.PREFIX[message.server.name]):]
        if command in Client.COMMAND_LIST:
            if command == "prefix":
                asyncio.get_event_loop().create_task(Client.do_prefix(message, tokens))
            elif command == "settc":
                asyncio.get_event_loop().create_task(Client.do_set_tc(message, tokens))
            elif command == "sesh":
                asyncio.get_event_loop().create_task(Client.do_sesh(message, tokens))
            elif command == "leave":
                asyncio.get_event_loop().create_task(Client.do_leave(message, tokens))
            elif command == "say":
                asyncio.get_event_loop().create_task(Client.do_say(message, tokens))
            else:
                asyncio.get_event_loop().create_task(Client.disc_client.send_message(message.channel, 'Sup bitch'))
        else:
            asyncio.get_event_loop().create_task(Client.disc_client.send_message(message.channel,
                                                                  "{} smoking gas again :joy::joy:".format(message.author.mention)))


if __name__ == '__main__':
    disc_client = Client()


