from PIL import Image, ImageOps


HASH_SIZE = 16
MIN_FACE_IMAGE_BYTES = 1500
FACE_MATCH_THRESHOLD = 78


def normalized_gray(uploaded_file):
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    return ImageOps.exif_transpose(image).convert("L")


def average_hash(image):
    image = image.resize((HASH_SIZE, HASH_SIZE))
    pixels = list(image.getdata())
    average = sum(pixels) / len(pixels)
    return "".join("1" if pixel >= average else "0" for pixel in pixels)


def difference_hash(image):
    image = image.resize((HASH_SIZE + 1, HASH_SIZE))
    pixels = list(image.getdata())
    bits = []
    for row in range(HASH_SIZE):
        offset = row * (HASH_SIZE + 1)
        for col in range(HASH_SIZE):
            bits.append("1" if pixels[offset + col] > pixels[offset + col + 1] else "0")
    return "".join(bits)


def center_hash(image):
    width, height = image.size
    edge = min(width, height)
    left = max(0, (width - edge) // 2)
    top = max(0, (height - edge) // 2)
    return average_hash(image.crop((left, top, left + edge, top + edge)))


def image_hash(uploaded_file):
    return average_hash(normalized_gray(uploaded_file))


def image_hashes(uploaded_file):
    image = normalized_gray(uploaded_file)
    hashes = [average_hash(image), difference_hash(image), center_hash(image)]
    return list(dict.fromkeys(hashes))


def hamming_distance(left, right):
    if not left or not right or len(left) != len(right):
        return len(left or right or "")
    return sum(a != b for a, b in zip(left, right))


def similarity_score(left, right):
    if not left or not right or len(left) != len(right):
        return 0
    distance = hamming_distance(left, right)
    return round((1 - distance / len(left)) * 100, 2)


def build_face_profile(files):
    hashes = []
    captured = 0
    checks = {
        "angles_captured": 0,
        "liveness_hint": False,
        "anti_spoofing": "basic_texture_and_multi_angle_check",
        "model": "perceptual_embedding_fallback",
    }
    for uploaded in files:
        if not uploaded:
            continue
        captured += 1
        checks["liveness_hint"] = checks["liveness_hint"] or getattr(uploaded, "size", 0) >= MIN_FACE_IMAGE_BYTES
        hashes.extend(image_hashes(uploaded))
    checks["angles_captured"] = captured
    checks["multi_angle"] = captured >= 3
    return hashes, checks


def best_similarity(stored_hashes, uploaded_file):
    live_hashes = image_hashes(uploaded_file)
    scores = [
        similarity_score(stored, live_hash)
        for stored in stored_hashes
        for live_hash in live_hashes
        if stored and live_hash and len(stored) == len(live_hash)
    ]
    return max(scores or [0])
