from django.urls import path

from .consumers import TicketListConsumer, TicketUpdateConsumer, UserEventConsumer

websocket_urlpatterns = [
    path("ws/events/", UserEventConsumer.as_asgi()),
    path("ws/tickets/", TicketListConsumer.as_asgi()),
    path("ws/tickets/<int:ticket_id>/", TicketUpdateConsumer.as_asgi()),
]
