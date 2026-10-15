import random
import string


def _random_numbers(count=10):
    """1~10 사이 랜덤 숫자를 공백으로 구분"""
    nums = [str(random.randint(1, 10)) for _ in range(count)]
    return " ".join(nums)


def random_blog_post():
    """블로그 글: 제목은 고정, 본문은 랜덤 숫자"""
    title = "오늘 하루도 수고 많으셨어요"
    body = _random_numbers(10)
    return title, body


def random_cafe_post():
    """카페 글: 제목은 고정, 본문은 랜덤 숫자"""
    title = "안녕하세요 오늘도 화이팅"
    body = _random_numbers(10)
    return title, body
