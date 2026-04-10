from setuptools import find_packages, setup


with open("requirements.txt") as f:
    install_requires = f.read().strip().splitlines()


setup(
    name="processedge_posnext_override",
    version="0.0.1",
    description="ProcessEdge POSNext overrides for ERPNext v16",
    author="ProcessEdge Solutions",
    author_email="processedgeng@gmail.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
