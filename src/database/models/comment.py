from src.database.models.base import Base
from typing import Optional, List
from sqlalchemy import (
    Text,
    ForeignKey,
    Integer,
    DateTime,
)
import datetime
from sqlalchemy.orm import mapped_column, Mapped, relationship


class CommentModel(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

    # Додайте поле для батьківського коментаря
    parent_comment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="comments")
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="comments")

    # Додайте зв'язки для ієрархії коментарів
    parent_comment: Mapped[Optional["CommentModel"]] = relationship(
        "CommentModel", remote_side=[id], back_populates="replies", lazy="joined"
    )
    replies: Mapped[List["CommentModel"]] = relationship(
        "CommentModel", back_populates="parent_comment", lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, user_id={self.user_id}, movie_id={self.movie_id}, text='{self.text[:20]}...')>"