from aiohttp import web
import aiofiles
import asyncio
import os
import logging
import argparse


async def archivate(request):
    archive_hash = request.match_info.get('archive_hash')
    archive_path = os.path.join(PHOTOS_DIR, archive_hash)
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
            archive_chunk = await archiving_process.stdout.read(CHUNK_SIZE)
            logging.debug('Sending archive chunk ...')
            await response.write(archive_chunk)
            if DELAY_BETWEEN_CHUNKS_SENDING:
                await asyncio.sleep(DELAY_BETWEEN_CHUNKS_SENDING)
            if not archive_chunk:
                break
    except (ConnectionResetError, asyncio.CancelledError):
        archiving_process.terminate()
        logging.debug('Sending file was cancelled')
        raise
    finally:
        response.force_close()
    logging.debug('Sending file was finished')
    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
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
    PHOTOS_DIR = args.photos_dir or os.getenv('PHOTOS_DIR', 'test_photos')
    CHUNK_SIZE = args.chunk_size or int(os.getenv('CHUNK_SIZE', '1024'))
    DELAY_BETWEEN_CHUNKS_SENDING = args.delay or float(
        os.getenv('DELAY_BETWEEN_CHUNKS_SENDING', '0')
    )
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archivate),
    ])
    web.run_app(app)
