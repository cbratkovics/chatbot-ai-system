
import pytest

from api.models.chat import ImageContent, Message, TextContent
from api.services.image_processor import ImageProcessor


@pytest.mark.asyncio
async def test_image_processor():
    processor = ImageProcessor()

    # Test base64 validation
    valid_base64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k="

    assert processor.validate_image_size(valid_base64)


def test_multimodal_message():
    # Test creating multi-modal message
    content = [
        TextContent(text="What's in this image?"),
        ImageContent(image_url={"url": "data:image/jpeg;base64,..."}),
    ]

    message = Message(session_id="test", content=content, role="user")

    assert len(message.content) == 2
    assert message.content[0].type == "text"
    assert message.content[1].type == "image_url"


@pytest.mark.asyncio
async def test_image_metadata_extraction():
    processor = ImageProcessor()

    # Test with small valid image
    small_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    metadata = await processor.extract_image_metadata(small_image)
    assert metadata.get("format") == "PNG"
    assert metadata.get("width") == 1
    assert metadata.get("height") == 1
