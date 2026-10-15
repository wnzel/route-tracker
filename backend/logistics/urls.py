from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("depots", views.DepotViewSet, basename="depot")
router.register("zones", views.ZoneViewSet, basename="zone")
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("drivers", views.DriverViewSet, basename="driver")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = router.urls
