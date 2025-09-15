import apsw


class ProjectDB:
    def __init__(self):
        self.connection = apsw.Connection(":memory:")
        self.cursor = self.connection.cursor()
        self._initialize_db()

    def _initialize_db(self):
        self.cursor.execute(
            """
            CREATE TABLE images (
                id INTEGER PRIMARY KEY,
                name TEXT,
                raster_path TEXT,
                width INTEGER,
                height INTEGER,
                dtype TEXT,
                crs TEXT,
                affine BLOB
            );
        """
        )
        self.cursor.execute(
            """
            CREATE TABLE stretches (
                id INTEGER PRIMARY KEY,
                type TEXT,
                params TEXT,
            )"""
        )
        self.cursor.execute(
            """
            CREATE TABLE bands (
                id INTEGER PRIMARY KEY,
                name TEXT,
                r REAL,
                g REAL,
                b REAL,
            )"""
        )
        self.cursor.execute(
            """
            CREATE TABLE band_image_links (
                image_id INTEGER,
                band_id INTEGER,
                FOREIGN KEY(image_id) REFERENCES images(id),
                FOREIGN KEY(band_id) REFERENCES bands(id))
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE band_image_links (
                stretch_id INTEGER,
                image_id INTEGER,
                FOREIGN KEY(stretch_id) REFERENCES stretches(id),
                FOREIGN KEY(image_id) REFERENCES images(id)
            )"""
        )
        self.cursor.execute(
            """
            CREATE TABLE rois (
                id INTEGER PRIMARY KEY,
                name TEXT,
                crs TEXT,
                geometry BLOB
                color TEXT
            )
                
            """
        )

    def save(self, path):
        with apsw.Connection(path) as file_connection:
            self.connection.backup("main", file_connection, "main")

    def load(self, path):
        with apsw.Connection(path) as file_connection:
            file_connection.backup("main", self.connection, "main")


if __name__ == "__main__":
    db = ProjectDB()
    db.save("test.db")
    while True:
        continue
