from aiohttp import web
import aiofiles
import asyncio
import os
import logging
import argparse
import functools


async def archivate(request,
                    photos_dir='test_photos',
                    chunk_size=1024,
                    delay_between_chunks_sending=0):
    archive_hash = request.match_info.get('archive_hash')
    archive_path = os.path.join(photos_dir, archive_hash)
    if not os.path.exists(archive_path):
        raise web.HTTPNotFound(reason='Архив не существует или был удален')
    archiving_process = await asyncio.subprocess.create_subprocess_shell(
        f'exec zip -r - "{archive_path}"',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'attachment; filename="archive.zip"'
    await response.prepare(request)
    try:
        while True:
            archive_chunk = await archiving_process.stdout.read(chunk_size)
            if not archive_chunk:
                break
            logging.debug('Sending archive chunk ...')
            await response.write(archive_chunk)
            if delay_between_chunks_sending:
                await asyncio.sleep(delay_between_chunks_sending)
    except asyncio.CancelledError:
        logging.debug('Sending file was cancelled')
        raise
    except ConnectionResetError:
        logging.debug('Connection reset by user')
        return
    finally:
        if os.path.exists(f'/proc/{archiving_process.pid}'):
            archiving_process.terminate()
        response.force_close()
    logging.debug('Sending file was finished')
    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--photos-dir',
                        type=str,
                        help='set directory for photos')
    parser.add_argument('--chunk-size',
                        type=int,
                        help='set archive chunk size in bytes')
    parser.add_argument('--debug',
                        action='store_true',
                        help='set debug mode')
    parser.add_argument('--delay',
                        type=float,
                        help='set delay between sending chunks in seconds')
    args = parser.parse_args()
    if args.debug or os.getenv('DEBUG') == '1':
        logging.basicConfig(level=logging.DEBUG)
    photos_dir = args.photos_dir or os.getenv('PHOTOS_DIR', 'test_photos')
    chunk_size = args.chunk_size or int(os.getenv('CHUNK_SIZE', '1024'))
    delay_between_chunks_sending = args.delay or float(
        os.getenv('DELAY_BETWEEN_CHUNKS_SENDING', '0')
    )
    handle_archive_page = functools.partial(
        archivate,
        photos_dir=photos_dir,
        chunk_size=chunk_size,
        delay_between_chunks_sending=delay_between_chunks_sending,
    )
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', handle_archive_page),
    ])
    web.run_app(app)


if __name__ == '__main__':
    main()
