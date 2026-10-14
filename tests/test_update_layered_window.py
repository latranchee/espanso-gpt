import unittest

from PIL import Image

from update_layered_window import to_premultiplied_bgra


def one_pixel(color: tuple[int, int, int, int]) -> bytes:
    return to_premultiplied_bgra(Image.new("RGBA", (1, 1), color))


class ToPremultipliedBgraTest(unittest.TestCase):
    def test_opaque_red_is_reordered_to_bgra(self) -> None:
        self.assertEqual(one_pixel((255, 0, 0, 255)), bytes([0, 0, 255, 255]))

    def test_half_transparent_color_is_premultiplied(self) -> None:
        self.assertEqual(one_pixel((200, 100, 50, 128)), bytes([25, 50, 100, 128]))

    def test_fully_transparent_pixel_is_black(self) -> None:
        self.assertEqual(one_pixel((200, 100, 50, 0)), bytes([0, 0, 0, 0]))


if __name__ == "__main__":
    unittest.main()
