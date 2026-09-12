from django.urls import path

from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('upload/<int:type_id>/', views.upload_document, name='upload'),
    path('view/<int:pk>/', views.view_document, name='view'),
    path('review/', views.reviewer_queue, name='reviewer_queue'),
    path('review/<int:pk>/', views.review_document, name='review'),
]