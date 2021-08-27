from __future__ import unicode_literals

import asyncio
import os
import traceback

import pytgcalls
from pyrogram import filters, idle
from pyrogram.errors.exceptions.bad_request_400 import \
    ChatAdminRequired
from pyrogram.raw.functions.phone import CreateGroupCall
from pyrogram.raw.types import InputPeerChannel
from pyrogram.types import Message

# Initialize db
import db

db.init()

from db import db
from functions import (CHAT_ID, app, get_default_service, play_song,
                       session, telegram, BITRATE)
from misc import HELP_TEXT, REPO_TEXT

running = False  # Tells if the queue is running or not
CLIENT_TYPE = pytgcalls.GroupCallFactory.MTPROTO_CLIENT_TYPE.PYROGRAM
PLAYOUT_FILE = "input.raw"
PLAY_LOCK = asyncio.Lock()
OUTGOING_AUDIO_BITRATE_KBIT = BITRATE


@app.on_message(
    filters.command("dj_vlados_help") 
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def help(_, message):
    await message.reply_text(HELP_TEXT, quote=False)


@app.on_message(
    filters.command("dj_vlados_join")
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def joinvc(_, message, manual=False):
    if "call" in db:
        return await message.reply_text(
            "__**Я уже за вертушками, долбоеб**__"
        )
    os.popen(f"cp etc/sample_input.raw {PLAYOUT_FILE}")
    vc = pytgcalls.GroupCallFactory(
        app, CLIENT_TYPE, OUTGOING_AUDIO_BITRATE_KBIT
    ).get_file_group_call(PLAYOUT_FILE)
    db["call"] = vc
    try:
        await vc.start(CHAT_ID)
    except Exception:
        peer = await app.resolve_peer(CHAT_ID)
        startVC = CreateGroupCall(
            peer=InputPeerChannel(
                channel_id=peer.channel_id,
                access_hash=peer.access_hash,
            ),
            random_id=app.rnd_id() // 9000000000,
        )
        try:
            await app.send(startVC)
            await vc.start(CHAT_ID)
        except ChatAdminRequired:
            del db["call"]
            return await message.reply_text(
                "Сделай меня админом со всеми правами и поиграю тебе пластинки"
            )
    await message.reply_text(
        "__**DJ Vlados ворвался за пульт и готов крутить музло.**__ \n\n**Псссс:** __Если нихуя не слышно,"
        + " напиши /dj_vlados_leave а потом /dj_vlados_join еще раз.__"
    )
    await message.delete()


@app.on_message(
    filters.command("dj_vlados_leave")
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def leavevc(_, message):
    if "call" in db:
        await db["call"].leave_current_group_call()
        await db["call"].stop()
        del db["call"]
    await message.reply_text("__**Пока уебки, для вас свой сет играл DJ Vlados**__")
    await message.delete()


@app.on_message(
    filters.command("volume")
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def volume_bot(_, message):
    usage = "**Настройки громкости:**\n/volume [1-200]"
    if len(message.command) != 2:
        return await message.reply_text(usage)
    if "call" not in db:
        return await message.reply_text("Я не у пульта")
    vc = db["call"]
    volume = int(message.text.split(None, 1)[1])
    if (volume < 1) or (volume > 200):
        return await message.reply_text(usage)
    try:
        await vc.set_my_volume(volume=volume)
    except ValueError:
        return await message.reply_text(usage)
    await message.reply_text(f"**Громкость выставил на {volume}**")


@app.on_message(
    filters.command("pause")
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def pause_song_func(_, message):
    if "call" not in db:
        return await message.reply_text("**Я не у пульта**")
    if "paused" in db:
        if db.get("paused"):
            return await message.reply_text("**Уже на паузе, чел**")
    db["paused"] = True
    db["call"].pause_playout()
    await message.reply_text(
        "**Воу воу воу, поставил на паузу. Давай скорее продолжим `/resume` **"
    )


@app.on_message(
    filters.command("resume")
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def resume_song(_, message):
    if "call" not in db:
        return await message.reply_text("**Я не у пульта**")
    if "paused" in db:
        if not db.get("paused"):
            return await message.reply_text("**Да уже играем музяку**")
    db["paused"] = False
    db["call"].resume_playout()
    await message.reply_text(
        "**Погнали дальше! Но если опять нужна пауза, ты знаешь — `/pause` **"
    )


@app.on_message(
    filters.command("skip") & ~filters.private & filters.chat(CHAT_ID)
)
async def skip_func(_, message):
    if "queue" not in db:
        await message.reply_text("**Я не у пульта**")
        return await message.delete()
    queue = db["queue"]
    if queue.empty() and ("playlist" not in db or not db["playlist"]):
        await message.reply_text(
            "__**Заявки на музыку пусты. Как и смысл твоей жизни**__"
        )
        return await message.delete()
    db["skipped"] = True
    await message.reply_text("__**Правильно, нахуй эту песенку! Следующая!**__")
    await message.delete()



@app.on_message(
    filters.command("play") & ~filters.private & filters.chat(CHAT_ID)
)
async def queuer(_, message):
    global running
    try:
        usage = """
**Как заказать музыку:**
__/play Название_песни__
__/play Ответом_на_файл__"""

        async with PLAY_LOCK:
            if (
                len(message.command) < 2
                and not message.reply_to_message
            ):
                return await message.reply_text(usage)
            if "call" not in db:
                return await message.reply_text(
                    "**Ты приходишь сюда, просишь что-то поставить... Но ты делаешь это неуважительно. Ты не предлагаешь мне сперва встать за пульт — /joinvc **"
                )
            if message.reply_to_message:
                if message.reply_to_message.audio:
                    service = "telegram"
                    song_name = message.reply_to_message.audio.title
                else:
                    return await message.reply_text(
                        "**Не, ответом на сообщение с файлом (mp3, wav, mp4 и тд)**"
                    )
            else:
                text = message.text.split("\n")[0]
                text = text.split(None, 2)[1:]
                service = text[0].lower()
                services = ["youtube", "saavn"]
                if service in services:
                    song_name = text[1]
                else:
                    service = get_default_service()
                    song_name = " ".join(text)
                if "http" in song_name or ".com" in song_name:
                    return await message.reply("Никаких ссылок")

            requested_by = message.from_user.first_name
            if "queue" not in db:
                db["queue"] = asyncio.Queue()
            if not db["queue"].empty() or db.get("running"):
                await message.reply_text("__**Добавил в очередь__**")

            await db["queue"].put(
                {
                    "service": service or telegram,
                    "requested_by": requested_by,
                    "query": song_name,
                    "message": message,
                }
            )
        if not db.get("running"):
            db["running"] = True
            await start_queue()
    except Exception as e:
        await message.reply_text(str(e))
        e = traceback.format_exc()
        print(e)


@app.on_message(
    filters.command("queue")
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def queue_list(_, message):
    if "queue" not in db:
        db["queue"] = asyncio.Queue()
    queue = db["queue"]
    if queue.empty():
        return await message.reply_text(
            "__**Заявки на музыку пусты. Как и смысл твоей жизни**__"
        )
    if (
        len(message.text.split()) > 1
        and message.text.split()[1].lower() == "plformat"
    ):
        pl_format = True
    else:
        pl_format = False
    text = ""
    for count, song in enumerate(queue._queue, 1):
        if not pl_format:
            text += (
                f"**{count}. {song['service']}** "
                + f"| __{song['query']}__  |  {song['requested_by']}\n"
            )
        else:
            text += song["query"] + "\n"
    if len(text) > 4090:
        return await message.reply_text(
            f"**У меня тут треков в количестве {queue.qsize()} шт. в заявках...**"
        )
    await message.reply_text(text)


# Queue handler


async def start_queue(message=None):
    while db:
        if "queue_breaker" in db and db.get("queue_breaker") != 0:
            db["queue_breaker"] -= 1
            if db["queue_breaker"] == 0:
                del db["queue_breaker"]
            break
        if db["queue"].empty():
            if "playlist" not in db or not db["playlist"]:
                db["running"] = False
                break
            else:
                await playlist(app, message, redirected=True)
        data = await db["queue"].get()
        service = data["service"]
        if service == "telegram":
            await telegram(data["message"])
        else:
            await play_song(
                data["requested_by"],
                data["query"],
                data["message"],
                service,
            )


@app.on_message(
    filters.command("delqueue")
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def clear_queue(_, message):
    global db
    if "call" not in db:
        return await message.reply_text("**Я не у пульта**")
    if ("queue" not in db or db["queue"].empty()) and (
        "playlist" not in db or not db["playlist"]
    ):
        return await message.reply_text("**Заявки уже и так пусты...**")
    db["playlist"] = False
    db["queue"] = asyncio.Queue()
    await message.reply_text("**Нахуй всё это, начинаем с чистого листа заявок**")


@app.on_message(
    filters.command("playlist")
    & ~filters.private
    & filters.chat(CHAT_ID)
)
async def playlist(_, message: Message, redirected=False):
    if message.reply_to_message:
        raw_playlist = message.reply_to_message.text
    elif len(message.text) > 9:
        raw_playlist = message.text[10:]
    else:
        usage = """
**Как юзать плейлист: да так же как и /play
Например:
    __**/playlist название_песни1
    название_песни2
    название_песни3**__"""

        return await message.reply_text(usage)
    if "call" not in db:
        return await message.reply_text("**Ты приходишь сюда, просишь что-то поставить... Но ты делаешь это неуважительно. Ты не предлагаешь мне сперва встать за пульт — /joinvc **")
    if "playlist" not in db:
        db["playlist"] = False
    if "running" in db and db.get("running"):
        db["queue_breaker"] = 1
    db["playlist"] = True
    db["queue"] = asyncio.Queue()
    for line in raw_playlist.split("\n"):
        services = ["youtube", "saavn"]
        if line.split()[0].lower() in services:
            service = line.split()[0].lower()
            song_name = " ".join(line.split()[1:])
        else:
            service = "youtube"
            song_name = line
        requested_by = message.from_user.first_name
        await db["queue"].put(
            {
                "service": service or telegram,
                "requested_by": requested_by,
                "query": song_name,
                "message": message,
            }
        )
    if not redirected:
        db["running"] = True
        await message.reply_text("**Начинаем играть плейлист**")
        await start_queue(message)


async def main():
    await app.start()
    print("Bot started!")
    await idle()
    await session.close()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
