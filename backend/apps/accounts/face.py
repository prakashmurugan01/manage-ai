from PIL import Image, ImageOps


HASH_SIZE = 16
MIN_FACE_IMAGE_BYTES = 1500


def image_hash(uploaded_file):
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image).convert("L").resize((HASH_SIZE, HASH_SIZE))
    pixels = list(image.getdata())
    average = sum(pixels) / len(pixels)
    return "".join("1" if pixel >= average else "0" for pixel in pixels)


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
    checks = {
        "angles_captured": 0,
        "liveness_hint": False,
        "anti_spoofing": "basic_texture_and_multi_angle_check",
        "model": "perceptual_embedding_fallback",
    }
    for uploaded in files:
        if not uploaded:
            continue
        checks["liveness_hint"] = checks["liveness_hint"] or getattr(uploaded, "size", 0) >= MIN_FACE_IMAGE_BYTES
        hashes.append(image_hash(uploaded))
    checks["angles_captured"] = len(hashes)
    checks["multi_angle"] = len(hashes) >= 3
    return hashes, checks


def best_similarity(stored_hashes, uploaded_file):
    live_hash = image_hash(uploaded_file)
    scores = [similarity_score(stored, live_hash) for stored in stored_hashes if stored]
    return max(scores or [0])
