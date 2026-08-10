from openbook.volumes import Volume, read_volumes


class FakeChapter:
    def __init__(self, body):
        self.body = body


ARCHIVE = """
<p>|| Volumes ||</p>
<p>[Prologue]</p><p>The Creation</p>
<p>[Volume 1] The Ascension (3 - 22)</p>
<p>[Volume 2]</p><p>The Apostle Of Fear (23 - 54)</p>
<p>[Volume 6] The Apostle Of</p><p>Love</p><p>(153 - 190)</p>
<p>[Volume 9]</p><p>The Scholar</p><p>(255 - XXX)</p>
"""


def test_the_volumes_are_read_out_of_the_archive():
    found = read_volumes([FakeChapter(ARCHIVE)])
    assert found["Volume 1"].title == "The Ascension"
    assert found["Volume 1"].first == 3
    assert found["Volume 1"].last == 22


def test_a_title_broken_across_lines_is_joined():
    # The exporter breaks a long line wherever it pleases, so this arrives as
    # "The Apostle Of" then "Love" then the chapters.
    found = read_volumes([FakeChapter(ARCHIVE)])
    assert found["Volume 6"].title == "The Apostle Of Love"


def test_a_volume_with_no_chapters_given_still_reads():
    found = read_volumes([FakeChapter(ARCHIVE)])
    assert found["Prologue"].title == "The Creation"
    assert found["Prologue"].first is None


def test_a_book_still_being_written_has_no_last_chapter():
    # The newest volume says XXX where its last chapter will go.
    found = read_volumes([FakeChapter(ARCHIVE)])
    assert found["Volume 9"].first == 255
    assert found["Volume 9"].last is None


def test_a_chapter_with_no_table_gives_nothing():
    assert read_volumes([FakeChapter("<p>Just a chapter.</p>")]) == {}


def test_the_two_forms_of_a_name():
    volume = Volume(name="Volume 1", title="The Ascension")
    assert volume.full == "Volume 1 The Ascension"
    assert volume.written == "Volume 1: The Ascension"


def test_a_volume_with_no_title_does_not_gain_a_colon():
    assert Volume(name="Volume 1", title="").written == "Volume 1"
